<script setup lang="ts">
/**
 * 教师演示正文。
 * 学员演示、教师分享详情、审核详情共用。
 * 开始练习的卡片不走这里，那里不能提前给出结论。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  source?: Record<string, any> | null
}>()

function pick<T>(camel: string, snake: string, fallback: T): T {
  const src = props.source || {}
  const value = src[camel] ?? src[snake]
  return (value ?? fallback) as T
}

const teachingPoints = computed(() => String(pick('teachingPoints', 'teaching_points', '')))
const goldDiagnosis = computed(() => String(pick('goldDiagnosis', 'gold_diagnosis', '')))
const goldGradeText = computed(() => String(pick('goldGradeText', 'gold_grade_text', '')))
const clinicalInfo = computed(() => String(pick('clinicalInfo', 'clinical_info', '')))
const description = computed(() => String(pick('description', 'description', '')))
const categoryText = computed(() => String(pick('categoryText', 'category_text', '')))
const difficultyText = computed(() => String(pick('difficultyText', 'difficulty_text', '')))
const lesions = computed<{ name: string; detail: string }[]>(() => {
  const raw = pick<any[]>('lesions', 'lesions', [])
  return Array.isArray(raw) ? raw : []
})
const annotations = computed<any[]>(() => {
  const raw = pick<any[]>('annotations', 'annotations', [])
  return Array.isArray(raw) ? raw : []
})
const lesionMaskUrl = computed(() => String(pick('lesionMaskUrl', 'lesion_mask_url', '')))

const images = computed(() => {
  const src = props.source || {}
  const paths = src.imagePaths || src.image_paths || {}
  const out: string[] = []
  const seen = new Set<string>()
  for (const side of ['OD', 'OS', 'OU', 'UK']) {
    const arr = paths[side]
    if (!Array.isArray(arr)) continue
    for (const url of arr) {
      if (!url || seen.has(url)) continue
      seen.add(url)
      out.push(url)
    }
  }
  return out
})

const active = ref(0)
const showMarks = computed(() => active.value === 0)
const mainImage = computed(() => images.value[active.value] || '')

const caption = computed(() => {
  if (!showMarks.value) return '标注和着色按第一张眼底图对齐，切换后只看原图。'
  const mask = !!lesionMaskUrl.value
  const boxes = annotations.value.length > 0
  if (mask && boxes) return '半透明着色是病灶范围，彩色框是带教标出的位置。'
  if (mask) return '半透明着色是病灶范围。这例没有矢量标注框。'
  if (boxes) return '彩色框是带教标出的位置，框旁写着病灶名称。'
  return '这张图没有金标准着色，也没有标注框。对照上面的结论自己看。'
})

const imgRef = ref<HTMLImageElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
let observer: ResizeObserver | null = null

function draw() {
  const img = imgRef.value
  const canvas = canvasRef.value
  if (!img || !canvas || !img.naturalWidth) return
  const w = img.clientWidth
  const h = img.clientHeight
  if (!w || !h) return
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, w, h)
  if (!showMarks.value) return
  const sx = w / img.naturalWidth
  const sy = h / img.naturalHeight
  for (const ann of annotations.value) {
    const pts = Array.isArray(ann?.points) ? ann.points : []
    if (pts.length < 2) continue
    const color = ann.color || '#00b42a'
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.setLineDash([5, 3])
    ctx.beginPath()
    const tool = ann.tool || 'rect'
    let labelX = pts[0].x * sx
    let labelY = pts[0].y * sy
    if (tool === 'rect') {
      const x = pts[0].x * sx
      const y = pts[0].y * sy
      const rw = (pts[1].x - pts[0].x) * sx
      const rh = (pts[1].y - pts[0].y) * sy
      ctx.strokeRect(x, y, rw, rh)
      labelX = x
      labelY = y
    } else {
      ctx.moveTo(pts[0].x * sx, pts[0].y * sy)
      for (const p of pts.slice(1)) ctx.lineTo(p.x * sx, p.y * sy)
      ctx.closePath()
      ctx.stroke()
    }
    if (ann.label) {
      ctx.setLineDash([])
      ctx.font = '12px sans-serif'
      ctx.fillStyle = color
      ctx.fillText(String(ann.label), labelX + 2, Math.max(14, labelY - 4))
    }
  }
}

function bindObserver() {
  observer?.disconnect()
  if (!imgRef.value || typeof ResizeObserver === 'undefined') return
  observer = new ResizeObserver(() => draw())
  observer.observe(imgRef.value)
}

watch([mainImage, annotations, () => showMarks.value], async () => {
  await nextTick()
  bindObserver()
  draw()
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div class="demo">
    <p v-if="categoryText || difficultyText" class="kind">
      {{ [categoryText, difficultyText].filter(Boolean).join(' · ') }}
    </p>

    <section>
      <h4>1. 先看什么</h4>
      <p v-if="teachingPoints" class="body">{{ teachingPoints }}</p>
      <p v-else class="empty">这份分享没有写带教要点。</p>
    </section>

    <section>
      <h4>2. 标准结论</h4>
      <p v-if="goldGradeText" class="grade">{{ goldGradeText }}</p>
      <p v-if="goldDiagnosis" class="body">{{ goldDiagnosis }}</p>
      <p v-else class="empty">这份分享没有写标准诊断。</p>
    </section>

    <section>
      <h4>3. 图上要找到的病灶</h4>
      <ul v-if="lesions.length" class="lesions">
        <li v-for="(item, i) in lesions" :key="i">
          <strong>{{ item.name }}</strong>
          <span v-if="item.detail">{{ item.detail }}</span>
        </li>
      </ul>
      <p v-else class="empty">没有列出病灶。正常眼底或未标注的病例会是这样。</p>
    </section>

    <section>
      <h4>4. 对照眼底图</h4>
      <p v-if="!images.length" class="empty">没有眼底图。</p>
      <template v-else>
        <div class="stage">
          <img ref="imgRef" class="fundus" :src="mainImage" alt="眼底" @load="draw" />
          <img
            v-if="showMarks && lesionMaskUrl"
            class="mask"
            :src="lesionMaskUrl"
            alt=""
          />
          <canvas ref="canvasRef" class="boxes" />
        </div>
        <p class="caption">{{ caption }}</p>
        <div v-if="images.length > 1" class="thumbs">
          <button
            v-for="(url, i) in images"
            :key="url"
            type="button"
            :class="{ on: i === active }"
            @click="active = i"
          >
            第 {{ i + 1 }} 张
          </button>
        </div>
      </template>
    </section>

    <section v-if="clinicalInfo">
      <h4>已知情况</h4>
      <p class="body">{{ clinicalInfo }}</p>
    </section>

    <section v-if="description">
      <h4>资料说明</h4>
      <p class="note">{{ description }}</p>
    </section>
  </div>
</template>

<style scoped>
.demo { display: flex; flex-direction: column; gap: 14px; }
.kind { margin: 0; font-size: 13px; color: #4e5969; }
section h4 {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 700;
  color: #1d2129;
}
.body, .empty, .note, .caption, .grade {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.65;
  font-size: 14px;
}
.body { color: #1d2129; }
.grade { color: #0e42d2; font-weight: 700; margin-bottom: 4px; }
.empty, .note, .caption { color: #4e5969; font-size: 13px; }
.lesions {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.lesions li {
  background: #f2f3f5;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  color: #1d2129;
}
.lesions span { margin-left: 6px; color: #4e5969; }
.stage {
  position: relative;
  width: min(100%, 640px);
  background: #0b0d12;
  border-radius: 8px;
  overflow: hidden;
}
.fundus { width: 100%; height: auto; display: block; }
.mask, .boxes {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.mask { opacity: 0.55; object-fit: fill; }
.thumbs { display: flex; gap: 8px; margin-top: 8px; }
.thumbs button {
  border: 1px solid #e5e6eb;
  background: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  color: #1d2129;
}
.thumbs button.on { border-color: #1677ff; color: #1677ff; }
</style>
