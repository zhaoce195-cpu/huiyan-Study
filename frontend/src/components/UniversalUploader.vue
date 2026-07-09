<script setup lang="ts">
/**
 * UniversalUploader 通用上传组件
 *
 * 职责：
 *  1. 前端文件类型 / 大小 / 危险扩展名校验（与后端 _DANGEROUS_EXT / COMMON_ALLOWED_EXT 对齐）
 *  2. autoUpload=true → 通过 CommonApi.uploadFile 调 POST /common/upload
 *  3. autoUpload=false → 仅校验后 emit('select', file)，由父组件接管自有上传通道
 *
 * 用法 A：自动上传到 /common/upload（学习资料附件）
 *   <UniversalUploader biz="learning" auto-upload @success="onDone" />
 *
 * 用法 B：仅做前端校验，再由父组件调专属接口（眼底图、case_image、头像）
 *   <UniversalUploader biz="screening" :auto-upload="false" :accept="['.jpg','.png']" @select="handle" />
 */
import { computed, ref } from 'vue'
import { ElMessage, ElUpload, ElIcon, ElButton } from 'element-plus'
import type { UploadRawFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { CommonApi } from '@/api'

type UploadFileResult = CommonApi.UploadFileResult

const props = withDefaults(
  defineProps<{
    /** 业务子目录，传给后端 save_common_upload(biz=...) */
    biz?: string
    /** 扩展名白名单（小写带点），如 ['.jpg','.png']。默认从 DEFAULT_ALLOWED 取 */
    accept?: string[]
    /** 大小上限 MB，默认 50（与后端一致） */
    maxSizeMB?: number
    /** UI 形式 */
    variant?: 'dragger' | 'button'
    /** 是否多选 */
    multiple?: boolean
    /** 是否自动上传到 /common/upload；false = 仅校验后 emit('select') */
    autoUpload?: boolean
    /** 拖拽区文案 */
    hint?: string
    /** 是否禁用 */
    disabled?: boolean
  }>(),
  {
    variant: 'dragger',
    multiple: false,
    autoUpload: true,
    maxSizeMB: 50,
  },
)

const emit = defineEmits<{
  (e: 'success', result: UploadFileResult): void
  (e: 'error', err: Error): void
  (e: 'select', file: File): void
}>()

/* 与后端 utils.py 保持一致 */
const DEFAULT_ALLOWED = [
  '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
  '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv',
  '.zip', '.rar', '.7z',
  '.mp4', '.mp3', '.wav',
]
const DANGEROUS_EXT = [
  '.exe', '.dll', '.bat', '.cmd', '.sh', '.ps1', '.js',
  '.vbs', '.scr', '.jar', '.com', '.msi',
]

const allowList = computed(() =>
  (props.accept && props.accept.length ? props.accept : DEFAULT_ALLOWED).map((s) => s.toLowerCase()),
)
const acceptAttr = computed(() => allowList.value.join(','))

const uploading = ref(false)

const getExt = (name: string): string => {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

/** 前端预校验，通过返回 File；不通过返回 null 并已弹 toast */
const validate = (raw: UploadRawFile | File): File | null => {
  const f = raw as File
  const ext = getExt(f.name || '')
  if (!ext) {
    ElMessage.warning('文件名缺少扩展名')
    return null
  }
  if (DANGEROUS_EXT.includes(ext)) {
    ElMessage.error(`不允许上传可执行 / 脚本类文件：${ext}`)
    return null
  }
  if (!allowList.value.includes(ext)) {
    ElMessage.warning(`不支持的文件类型：${ext}`)
    return null
  }
  if (f.size <= 0) {
    ElMessage.warning('上传文件为空')
    return null
  }
  if (f.size > props.maxSizeMB * 1024 * 1024) {
    ElMessage.warning(`文件最大允许 ${props.maxSizeMB}MB`)
    return null
  }
  return f
}

const beforeUpload = async (raw: UploadRawFile) => {
  const file = validate(raw)
  if (!file) return false

  if (!props.autoUpload) {
    emit('select', file)
    return false  // 阻止 el-upload 自动 POST
  }

  uploading.value = true
  try {
    const result = await CommonApi.uploadFile(file, props.biz)
    if (result) {
      ElMessage.success('上传成功')
      emit('success', result)
    }
  } catch (err: any) {
    emit('error', err instanceof Error ? err : new Error(String(err)))
  } finally {
    uploading.value = false
  }
  return false
}
</script>

<template>
  <el-upload
    class="universal-uploader"
    :class="`uu-${variant}`"
    :show-file-list="false"
    :auto-upload="false"
    :before-upload="beforeUpload"
    :multiple="multiple"
    :accept="acceptAttr"
    :disabled="disabled || uploading"
    :drag="variant === 'dragger'"
  >
    <template v-if="variant === 'dragger'">
      <el-icon class="uu-icon"><UploadFilled /></el-icon>
      <div class="uu-text">
        <slot>{{ hint || '点击或拖拽文件至此处' }}</slot>
      </div>
      <div class="uu-meta">
        支持 {{ allowList.join(' / ') }} · 单文件 ≤ {{ maxSizeMB }}MB
      </div>
    </template>
    <el-button v-else type="primary" :loading="uploading" :disabled="disabled">
      <slot>选择文件</slot>
    </el-button>
  </el-upload>
</template>

<style scoped>
.universal-uploader {
  display: inline-block;
  width: 100%;
}
.uu-icon {
  font-size: 40px;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
.uu-text {
  font-size: 14px;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}
.uu-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
