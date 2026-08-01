<script setup lang="ts">
/**
 * Cornerstone3D 技术验证（spike）
 *
 * 目的：在全量替换阅片内核之前，先确认三件事——
 *   1. Cornerstone3D 能否渲染我们生成的 VL Photographic（JPEG 内嵌）实例；
 *   2. 走后端 WADO-RS 透传时传输量是否正确
 *      （应约 0.3 MB；漏写 transfer-syntax 会变成 34.94 MB）；
 *   3. SEG 的分段元数据能否正确读到。
 *
 * 这不是最终阅片页，只做最小验证，确认可行后再做完整替换。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ReadingApi } from '@/api'

const CASE_NO = 'IDRID-T-IDRiD_01'

const viewportRef = ref<HTMLDivElement | null>(null)
const status = ref<'idle' | 'loading' | 'ok' | 'failed'>('idle')
const message = ref('')
const info = ref<Record<string, any>>({})
const segments = ref<Array<{ number: number; label: string }>>([])
const transferBytes = ref(0)
const segOverlay = ref(false)
const segError = ref('')
const maskLayers = ref<Array<{label:string;url:string;color:string}>>([])
const maskBytes = ref(0)

let renderingEngine: any = null

const RENDERING_ENGINE_ID = 'huiyan-spike-engine'
const VIEWPORT_ID = 'huiyan-spike-viewport'

/** 统计经代理传输的字节数，用于验证传输语法是否生效 */
function installTransferMeter() {
  const origOpen = XMLHttpRequest.prototype.open
  const origSend = XMLHttpRequest.prototype.send
  XMLHttpRequest.prototype.open = function (this: any, ...args: any[]) {
    this.__huiyanUrl = args[1]
    return origOpen.apply(this, args as any)
  }
  XMLHttpRequest.prototype.send = function (this: any, ...args: any[]) {
    this.addEventListener('load', () => {
      if (String(this.__huiyanUrl || '').includes('/dicomweb/wado/')) {
        const len = Number(this.getResponseHeader('content-length') || 0)
        if (len) transferBytes.value += len
      }
    })
    return origSend.apply(this, args as any)
  }
}

async function run() {
  status.value = 'loading'
  message.value = '正在初始化 Cornerstone3D…'

  try {
    // Cornerstone3D v5 的初始化方式与 v1/v2 不同：
    //   · 已移除 external.cornerstone / external.dicomParser 与 configure()
    //   · 改为各包各自 init()，请求头通过 init 的 beforeSend 选项设置
    // 沿用旧写法会在模块求值阶段抛
    // "Class extends value undefined is not a constructor or null"。
    const cornerstone = await import('@cornerstonejs/core')
    const dicomImageLoader = await import('@cornerstonejs/dicom-image-loader')

    const { RenderingEngine, Enums } = cornerstone
    await cornerstone.init()

    const token = localStorage.getItem('huiyan_token') || ''
    dicomImageLoader.init({
      maxWebWorkers: 1,
      beforeSend(_xhr: XMLHttpRequest, _imageId: string,
                 defaultHeaders: Record<string, string>) {
        // 返回值会并入请求头；影像经后端透传，凭据不下放到 PACS
        return token
          ? { ...defaultHeaders, Authorization: `Bearer ${token}` }
          : defaultHeaders
      }
    })

    message.value = '正在查询病例影像…'
    const summary = await ReadingApi.getCaseDicom(CASE_NO)
    const image = summary.images?.[0]
    const seg = summary.segmentations?.[0]
    if (!image) throw new Error('该病例在 PACS 中没有原始影像')

    info.value = {
      病例: CASE_NO,
      原始影像张数: summary.imageCount,
      分割实例数: summary.segmentationCount,
      眼别: image.eyeText,
      尺寸: `${image.columns} × ${image.rows}`,
      模态: image.modality
    }
    segments.value = summary.segmentations?.[0]?.segments || []

    // wadors imageId 指向后端透传接口
    const root = `${window.location.origin}/api/v1/dicomweb/wado`
    const studyPath = `${root}/studies/${image.studyInstanceUid}`
    const imageId =
      `wadors:${studyPath}` +
      `/series/${image.seriesInstanceUid}` +
      `/instances/${image.sopInstanceUid}/frames/1`

    // wadors 加载器不会自己去取元数据，必须先注册。
    // 少了这一步，解码时读不到 imagePixelModule，
    // 报 "Cannot read properties of undefined (reading 'samplesPerPixel')"。
    message.value = '正在注册影像元数据…'
    const metaResp = await fetch(`${studyPath}/metadata`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/dicom+json'
      }
    })
    if (!metaResp.ok) throw new Error(`取元数据失败：HTTP ${metaResp.status}`)
    const studyMeta = await metaResp.json()

    const SOP_UID_TAG = '00080018'
    for (const inst of studyMeta) {
      const uid = inst?.[SOP_UID_TAG]?.Value?.[0]
      if (!uid) continue
      const id =
        `wadors:${studyPath}/series/${inst['0020000E']?.Value?.[0]}` +
        `/instances/${uid}/frames/1`
      dicomImageLoader.wadors.metaDataManager.add(id, inst)
    }

    message.value = '正在加载影像…'
    installTransferMeter()

    renderingEngine = new RenderingEngine(RENDERING_ENGINE_ID)
    renderingEngine.enableElement({
      viewportId: VIEWPORT_ID,
      type: Enums.ViewportType.STACK,
      element: viewportRef.value as HTMLDivElement
    })
    const viewport: any = renderingEngine.getViewport(VIEWPORT_ID)
    await viewport.setStack([imageId])
    viewport.render()

    // setStack 不会因解码失败而抛异常，必须显式校验真的取到了像素，
    // 否则页面会在图没出来的情况下显示「渲染成功」。
    const rendered = viewport.getImageData?.()
    if (!rendered || !rendered.dimensions) {
      throw new Error('影像未能解码：viewport 中没有像素数据')
    }
    info.value['解码尺寸'] = rendered.dimensions.slice(0, 2).join(' × ')

    // ---- 叠加金标准分割（DICOM SEG → labelmap）----
    if (seg?.sopInstanceUid) {
      try {
        message.value = '正在加载病灶分割…'
        await overlaySegmentation(seg, token)
        segOverlay.value = true
      } catch (e: any) {
        // 分割叠加失败不应让整个验证判为失败：
        // 原图渲染是主线，叠加是增量能力，如实分开报告
        segError.value = e?.message || String(e)
      }
    }

    status.value = 'ok'
    message.value = '渲染完成'
  } catch (e: any) {
    status.value = 'failed'
    message.value = e?.message || String(e)
    ElMessage.error('spike 失败：' + message.value)
  }
}

/**
 * 叠加金标准分割。
 *
 * 不使用 Cornerstone3D 的 SEG 适配器：该适配器按断层类影像设计，
 * 要求 SEG 携带患者坐标系方位（ImageOrientationPatient）。
 * 眼底照是二维摄影本就没有这一概念，硬要适配只能往 DICOM 里
 * 写入伪造的空间信息——不可接受。
 *
 * 改由服务端把每个分段渲染成带透明通道的 PNG，前端按普通图层叠加：
 * 不依赖任何三维几何假设，传输量也从 5.98 MB 降到约 214 KB。
 */
async function overlaySegmentation(seg: any, token: string) {
  const colors = ['255,64,64', '255,170,0', '80,220,120', '90,170,255']
  const layers: Array<{ label: string; url: string; color: string }> = []

  for (const s of seg.segments || []) {
    const color = colors[(s.number - 1) % colors.length]
    const url =
      `/api/v1/dicomweb/segmentations/${seg.sopInstanceUid}` +
      `/segments/${s.number}/mask.png?color=${encodeURIComponent(color)}`
    const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    if (!resp.ok) throw new Error(`分段 ${s.number} 掩码取回失败：HTTP ${resp.status}`)
    const blob = await resp.blob()
    maskBytes.value += blob.size
    layers.push({ label: s.label, url: URL.createObjectURL(blob), color })
  }
  maskLayers.value = layers
}

onMounted(run)
onBeforeUnmount(() => {
  try {
    renderingEngine?.destroy?.()
  } catch {
    /* 忽略 */
  }
})
</script>

<template>
  <div class="spike">
    <header class="head">
      <h2>Cornerstone3D 技术验证</h2>
      <p class="sub">
        替换阅片内核前的最小验证：渲染能力 · 传输量 · SEG 元数据
      </p>
    </header>

    <div class="body">
      <div class="viewport-wrap">
        <div ref="viewportRef" class="viewport"></div>
        <!-- 分割掩码按普通图层叠加，与影像同一像素网格，逐像素对齐 -->
        <img
          v-for="l in maskLayers"
          :key="l.label"
          :src="l.url"
          class="mask-layer"
          :alt="l.label"
        />
        <div v-if="status !== 'ok'" class="overlay" :class="status">
          {{ message || '准备中…' }}
        </div>
      </div>

      <aside class="panel">
        <section>
          <h3>状态</h3>
          <p :class="['state', status]">
            {{ status === 'ok' ? '渲染成功' : status === 'failed' ? '失败' : '进行中' }}
          </p>
          <p class="msg">{{ message }}</p>
        </section>

        <section>
          <h3>病例信息</h3>
          <div v-for="(v, k) in info" :key="k" class="kv">
            <span class="k">{{ k }}</span><span class="v">{{ v }}</span>
          </div>
        </section>

        <section>
          <h3>传输量校验</h3>
          <div class="kv">
            <span class="k">经代理传输</span>
            <span class="v strong">{{ (transferBytes / 1048576).toFixed(2) }} MB</span>
          </div>
          <p class="hint">
            预期约 0.3 MB。若接近 35 MB，说明传输语法未生效，
            服务端会把内嵌 JPEG 转码成未压缩再发。
          </p>
        </section>

        <section>
          <h3>病灶分段（来自 DICOM SEG）</h3>
          <ul v-if="segments.length" class="segs">
            <li v-for="s in segments" :key="s.number">#{{ s.number }} {{ s.label }}</li>
          </ul>
          <p v-else class="hint">未读到分段</p>
          <div class="kv" style="margin-top:8px">
            <span class="k">叠加显示</span>
            <span class="v" :class="segOverlay ? 'ok' : 'bad'">
              {{ segOverlay ? `已叠加 ${maskLayers.length} 层` : '未叠加' }}
            </span>
          </div>
          <div v-if="maskBytes" class="kv">
            <span class="k">掩码传输</span>
            <span class="v">{{ (maskBytes / 1024).toFixed(0) }} KB</span>
          </div>
          <p v-if="segError" class="hint" style="color:#ff9a9a">
            叠加失败：{{ segError }}
          </p>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.spike {
  min-height: 100vh;
  background: #0f1014;
  color: #e5e6eb;
  padding: 16px 20px;
}
.head h2 {
  margin: 0;
  font-size: 18px;
}
.sub {
  margin: 4px 0 14px;
  color: #8a8f99;
  font-size: 13px;
}
.body {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.viewport-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
}
.mask-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}
.viewport {
  width: 100%;
  height: 70vh;
  background: #000;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
}
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b8bcc4;
  font-size: 14px;
  background: rgba(0, 0, 0, 0.55);
  border-radius: 6px;
  padding: 0 24px;
  text-align: center;
}
.overlay.failed {
  color: #ff7875;
}
.panel {
  width: 330px;
  flex-shrink: 0;
}
.panel section {
  margin-bottom: 18px;
  padding: 12px 14px;
  background: #16181e;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
}
.panel h3 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #cdd2da;
}
.state {
  margin: 0;
  font-weight: 700;
}
.state.ok {
  color: #52c41a;
}
.state.failed {
  color: #ff7875;
}
.state.loading {
  color: #f5c34b;
}
.msg {
  margin: 6px 0 0;
  color: #8a8f99;
  font-size: 12px;
  word-break: break-all;
}
.kv {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 3px 0;
  font-size: 13px;
}
.k {
  color: #8a8f99;
}
.v.ok {
  color: #52c41a;
  font-weight: 700;
}
.v.bad {
  color: #f5c34b;
}
.v.strong {
  font-weight: 700;
  color: #7cc4ff;
}
.hint {
  margin: 8px 0 0;
  color: #6f757f;
  font-size: 12px;
  line-height: 1.6;
}
.segs {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.9;
}
</style>
