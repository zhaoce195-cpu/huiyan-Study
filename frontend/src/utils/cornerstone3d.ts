/**
 * Cornerstone3D 阅片内核
 *
 * 替换原先的 cornerstone-core v2（legacy）。动因不是「换个新版本」，
 * 而是病例已全面 DICOM 化并进了 PACS：legacy 的 web-image-loader
 * 读不了 DICOMweb，阅片端就只能继续读 /static 下的 JPG，
 * 与影像归档各说各话。
 *
 * 两个加载器、一条渲染路径：
 *   wadors:  → PACS 中的 DICOM（经后端透传，凭据不下放）
 *   web:     → 尚未进 PACS 的遗留 JPG/PNG
 * 上层的视口、工具、坐标换算、标注绘制完全一致，
 * 不因影像来源分叉——分叉出来的第二条路必然缺测试、先腐坏。
 *
 * v5 的初始化方式与 v1/v2 不同：已移除 external.cornerstone 与
 * configure()，改为各包各自 init()。沿用旧写法会在模块求值阶段抛
 * "Class extends value undefined is not a constructor or null"。
 */

let corePromise: Promise<any> | null = null

export interface CoreBundle {
  cornerstone: any
  dicomImageLoader: any
}

const authToken = (): string => localStorage.getItem('huiyan_token') || ''

/* =========================================================
 * 遗留 JPG/PNG 加载器
 *
 * Cornerstone3D 官方不提供 web 影像加载器（它面向 DICOM）。
 * 这里实现最小可用的一版：把图解码到离屏 canvas 取 RGBA，
 * 并注册对应的元数据，使其在视口里与 DICOM 表现一致。
 * ========================================================= */

const webImageCache = new Map<string, any>()

const loadWebImage = (imageId: string): { promise: Promise<any> } => {
  const cached = webImageCache.get(imageId)
  if (cached) return { promise: Promise.resolve(cached) }

  const url = imageId.replace(/^web:/, '')
  const promise = new Promise<any>((resolve, reject) => {
    const img = new Image()
    // 同源资源；带上凭据以便后端按登录态返回
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) return reject(new Error('无法创建 2D 上下文'))
      ctx.drawImage(img, 0, 0)
      const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height)

      // Cornerstone3D 的彩色栈用 RGB 三通道；这里丢掉 alpha。
      // 眼底照没有透明通道，丢掉不会损失信息。
      const rgb = new Uint8Array(canvas.width * canvas.height * 3)
      for (let i = 0, j = 0; i < data.length; i += 4, j += 3) {
        rgb[j] = data[i]
        rgb[j + 1] = data[i + 1]
        rgb[j + 2] = data[i + 2]
      }

      const image = {
        imageId,
        minPixelValue: 0,
        maxPixelValue: 255,
        slope: 1,
        intercept: 0,
        windowCenter: 128,
        windowWidth: 255,
        voiLUTFunction: 'LINEAR',
        getPixelData: () => rgb,
        rows: canvas.height,
        columns: canvas.width,
        height: canvas.height,
        width: canvas.width,
        color: true,
        rgba: false,
        numberOfComponents: 3,
        // 眼底照没有真实的物理像素间距。这里填 1 只是为了让
        // 视口有个一致的世界坐标尺度，不代表 1 mm——
        // 因此测量工具在非 DICOM 影像上只报像素，不报毫米。
        columnPixelSpacing: 1,
        rowPixelSpacing: 1,
        invert: false,
        sizeInBytes: rgb.length,
        preScale: { scaled: false }
      }
      webImageCache.set(imageId, image)
      resolve(image)
    }
    img.onerror = () => reject(new Error(`影像加载失败：${url}`))
    img.src = url
  })

  return { promise }
}

/** web: 影像的元数据供给。缺了它解码阶段读不到 imagePixelModule */
const webMetaDataProvider = (type: string, imageId: string) => {
  if (typeof imageId !== 'string' || !imageId.startsWith('web:')) return undefined
  const image = webImageCache.get(imageId)
  if (!image) return undefined

  if (type === 'imagePixelModule') {
    return {
      photometricInterpretation: 'RGB',
      rows: image.rows,
      columns: image.columns,
      samplesPerPixel: 3,
      bitsAllocated: 8,
      bitsStored: 8,
      highBit: 7,
      pixelRepresentation: 0,
      planarConfiguration: 0
    }
  }
  if (type === 'imagePlaneModule') {
    return {
      rows: image.rows,
      columns: image.columns,
      imageOrientationPatient: [1, 0, 0, 0, 1, 0],
      imagePositionPatient: [0, 0, 0],
      // 见上：间距为无量纲的 1，不是毫米
      pixelSpacing: [1, 1],
      rowPixelSpacing: 1,
      columnPixelSpacing: 1,
      rowCosines: [1, 0, 0],
      columnCosines: [0, 1, 0]
    }
  }
  if (type === 'voiLutModule') {
    return { windowWidth: [255], windowCenter: [128] }
  }
  if (type === 'modalityLutModule') {
    return { rescaleSlope: 1, rescaleIntercept: 0 }
  }
  if (type === 'generalSeriesModule') {
    return { modality: 'OP' }
  }
  return undefined
}

/** 初始化一次；并发调用共用同一个 Promise，避免重复 init */
export const ensureCornerstone3D = (): Promise<CoreBundle> => {
  if (corePromise) return corePromise

  corePromise = (async () => {
    const cornerstone = await import('@cornerstonejs/core')
    const dicomImageLoader = await import('@cornerstonejs/dicom-image-loader')
    const cornerstoneTools = await import('@cornerstonejs/tools')

    await cornerstone.init()

    // 工具库必须在任何元素被 enable 之前初始化。
    //
    // init() 注册的是「元素启用时给它绑定工具事件」的监听器。若某个元素
    // 先于 init 被 enable，它就永远错过那次绑定 —— 之后 addTool、
    // setToolActive 全部「成功」，工具组里也查得到 Pan=Active，
    // 但鼠标事件到不了工具：平移、缩放、窗位、测量通通没反应，且不报错。
    //
    // 放在这里而不是组件里，就是为了保证它先于组件创建 RenderingEngine。
    await cornerstoneTools.init()

    dicomImageLoader.init({
      maxWebWorkers: Math.min(navigator.hardwareConcurrency || 2, 4),
      beforeSend(
        _xhr: XMLHttpRequest,
        _imageId: string,
        defaultHeaders: Record<string, string>
      ) {
        // 影像经后端透传，PACS 凭据始终留在服务端
        const token = authToken()
        return token
          ? { ...defaultHeaders, Authorization: `Bearer ${token}` }
          : defaultHeaders
      }
    })

    cornerstone.imageLoader.registerImageLoader('web', loadWebImage as any)
    cornerstone.metaData.addProvider(webMetaDataProvider as any, 10000)

    return { cornerstone, dicomImageLoader }
  })().catch((err) => {
    // 失败不要留下一个已 resolve 的坏 Promise，否则后续调用全部拿到坏内核
    corePromise = null
    throw err
  })

  return corePromise
}

/* =========================================================
 * imageId 构造
 * ========================================================= */

const wadoRoot = () => `${window.location.origin}/api/v1/dicomweb/wado`

export const studyPathOf = (studyInstanceUid: string): string =>
  `${wadoRoot()}/studies/${studyInstanceUid}`

export const wadorsImageId = (
  studyInstanceUid: string,
  seriesInstanceUid: string,
  sopInstanceUid: string,
  frame = 1
): string =>
  `wadors:${studyPathOf(studyInstanceUid)}` +
  `/series/${seriesInstanceUid}/instances/${sopInstanceUid}/frames/${frame}`

/** 站内相对路径转绝对；与旧 toImageId 的处理保持一致 */
export const webImageId = (url: string): string => {
  if (!url) return ''
  const t = url.trim()
  if (/^https?:\/\//i.test(t)) return `web:${t}`
  if (t.startsWith('//')) return `web:${window.location.protocol}${t}`
  if (t.startsWith('/')) return `web:${window.location.origin}${t}`
  if (/^[a-z]+:/i.test(t)) return `web:${t}`
  return `web:${new URL(t, window.location.href).toString()}`
}

/**
 * 注册整个 study 的 DICOM 元数据。
 *
 * wadors 加载器不会自己去取元数据，必须先注册。少了这一步，
 * 解码时读不到 imagePixelModule，报
 * "Cannot read properties of undefined (reading 'samplesPerPixel')"。
 */
export const registerStudyMetadata = async (
  dicomImageLoader: any,
  studyInstanceUid: string
): Promise<number> => {
  const studyPath = studyPathOf(studyInstanceUid)
  const resp = await fetch(`${studyPath}/metadata`, {
    headers: {
      Authorization: `Bearer ${authToken()}`,
      Accept: 'application/dicom+json'
    }
  })
  if (!resp.ok) throw new Error(`取影像元数据失败：HTTP ${resp.status}`)
  const studyMeta = await resp.json()

  const SOP_UID = '00080018'
  const SERIES_UID = '0020000E'
  let count = 0
  for (const inst of studyMeta) {
    const sop = inst?.[SOP_UID]?.Value?.[0]
    const series = inst?.[SERIES_UID]?.Value?.[0]
    if (!sop || !series) continue
    dicomImageLoader.wadors.metaDataManager.add(
      wadorsImageId(studyInstanceUid, series, sop),
      inst
    )
    count += 1
  }
  return count
}

const metadataDone = new Map<string, Promise<number>>()

/**
 * 确保某个 wadors imageId 的元数据已注册。
 *
 * study UID 直接从 imageId 里解析，不要求调用方额外传参、也不要求
 * 父子组件之间保证调用顺序 —— 顺序约定这种东西迟早会有人漏掉，
 * 漏掉的表现是解码时报 samplesPerPixel 读不到，很难定位。
 *
 * 同一 study 只注册一次；并发调用共用同一个 Promise。
 */
export const ensureMetadataFor = async (
  dicomImageLoader: any,
  imageId: string
): Promise<void> => {
  if (!imageId.startsWith('wadors:')) return
  const m = imageId.match(/\/studies\/([^/]+)\//)
  if (!m) return
  const studyUid = m[1]

  let job = metadataDone.get(studyUid)
  if (!job) {
    job = registerStudyMetadata(dicomImageLoader, studyUid)
    metadataDone.set(studyUid, job)
  }
  try {
    await job
  } catch (err) {
    // 失败不留缓存，下次可重试；否则一次网络抖动会让该病例永远打不开
    metadataDone.delete(studyUid)
    throw err
  }
}

/* =========================================================
 * DICOM SEG 病灶分割掩码
 *
 * 不走 Cornerstone3D 的 SEG 适配器：该适配器按断层影像设计，
 * 要求 SEG 携带患者坐标系方位（ImageOrientationPatient）。
 * 眼底照是二维摄影本就没有这一概念，硬要适配只能往 DICOM 里
 * 写入伪造的空间信息 —— 不可接受。
 *
 * 改由服务端把每个分段渲染成带透明通道的 PNG，前端按图层叠加：
 * 掩码与影像同一像素网格，逐像素对齐，不依赖任何三维几何假设，
 * 传输量也从 5.98 MB 降到约 214 KB。
 * ========================================================= */

export interface SegmentMask {
  number: number
  label: string
  color: string
  image: HTMLImageElement
}

const maskCache = new Map<string, HTMLImageElement>()

/** 分段掩码的配色：与病灶标签同一套，图例才对得上 */
export const SEGMENT_COLORS: Record<string, string> = {
  微动脉瘤: '#fadb14',
  视网膜出血: '#f53f3f',
  出血: '#f53f3f',
  硬性渗出: '#ff7d00',
  渗出: '#ff7d00',
  软性渗出: '#52c41a',
  棉绒斑: '#52c41a',
  视盘: '#1677ff'
}

const FALLBACK_COLORS = ['#f53f3f', '#ff7d00', '#fadb14', '#52c41a', '#1677ff']

const hexToRgbTriplet = (hex: string): string => {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`
}

/**
 * 取回某个 SEG 实例的全部分段掩码。
 *
 * 掩码要带鉴权取，所以走 fetch + blob，而不是直接把 URL 丢给 <img>。
 * 某个分段取失败不影响其它分段 —— 少一层掩码总好过整个金标准不显示。
 */
export const loadSegmentMasks = async (
  sopInstanceUid: string,
  segments: Array<{ number: number; label: string }>
): Promise<SegmentMask[]> => {
  const out: SegmentMask[] = []
  await Promise.all(
    segments.map(async (s, idx) => {
      const color = SEGMENT_COLORS[s.label] || FALLBACK_COLORS[idx % FALLBACK_COLORS.length]
      const key = `${sopInstanceUid}#${s.number}`
      let image = maskCache.get(key)
      if (!image) {
        const url =
          `/api/v1/dicomweb/segmentations/${sopInstanceUid}` +
          `/segments/${s.number}/mask.png?color=${encodeURIComponent(hexToRgbTriplet(color))}`
        const resp = await fetch(url, {
          headers: { Authorization: `Bearer ${authToken()}` }
        })
        if (!resp.ok) return
        const blob = await resp.blob()
        const objectUrl = URL.createObjectURL(blob)
        image = await new Promise<HTMLImageElement>((resolve, reject) => {
          const im = new Image()
          im.onload = () => resolve(im)
          im.onerror = () => reject(new Error('掩码解码失败'))
          im.src = objectUrl
        }).catch(() => undefined as any)
        if (!image) return
        maskCache.set(key, image)
      }
      out.push({ number: s.number, label: s.label, color, image })
    })
  )
  // Promise.all 的完成顺序不定，按分段号排回来，图层次序才稳定
  return out.sort((a, b) => a.number - b.number)
}

/* =========================================================
 * 坐标换算
 *
 * 标注一律以「影像像素坐标」存库，与显示无关——
 * 换了缩放、换了内核、换了屏幕都不影响既有标注的位置。
 * 这两个函数是像素坐标与屏幕坐标之间唯一的桥。
 * ========================================================= */

export const makeCoordMapper = (cornerstone: any, viewport: any) => {
  const { utilities } = cornerstone

  const imageId = (): string | undefined =>
    viewport?.getCurrentImageId?.() || viewport?.getImageIds?.()?.[0]

  return {
    /** 影像像素 → canvas 像素 */
    pixelToCanvas(x: number, y: number): { x: number; y: number } {
      const id = imageId()
      if (!id) return { x, y }
      const world = utilities.imageToWorldCoords(id, [x, y])
      if (!world) return { x, y }
      const [cx, cy] = viewport.worldToCanvas(world)
      return { x: cx, y: cy }
    },

    /** canvas 像素 → 影像像素 */
    canvasToPixel(cx: number, cy: number): { x: number; y: number } {
      const id = imageId()
      if (!id) return { x: cx, y: cy }
      const world = viewport.canvasToWorld([cx, cy])
      const image = utilities.worldToImageCoords(id, world)
      if (!image) return { x: cx, y: cy }
      return { x: image[0], y: image[1] }
    }
  }
}
