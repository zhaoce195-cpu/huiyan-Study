<script setup lang="ts">
/**
 * 我的教学分享（教师/管理员）
 * - 临时分享 + 入库申请 一并展示
 * - 状态筛选 + 收回 + 详情查看
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, View, RemoveFilled } from '@element-plus/icons-vue'
import { CommonApi, LearningApi, TeachingApi } from '@/api'
import UniversalUploader from '@/components/UniversalUploader.vue'
import TeachingDemoBody from './components/TeachingDemoBody.vue'

type Share = TeachingApi.TeachingShare

const list = ref<Share[]>([])
const loading = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const filter = reactive({
  shareType: '' as TeachingApi.ShareType | '',
  status: '' as TeachingApi.ShareStatus | '',
})

const statusMap: Record<string, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
  SHARING: { label: '分享中', type: 'success' },
  EXPIRED: { label: '已过期', type: 'info' },
  REVOKED: { label: '已收回', type: 'info' },
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '已通过', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
  SHELVED: { label: '已下架', type: 'info' },
}

const fetchList = async () => {
  loading.value = true
  try {
    const r = await TeachingApi.getMyShares({
      page: pagination.page,
      pageSize: pagination.pageSize,
      shareType: filter.shareType || undefined,
      status: filter.status || undefined,
    })
    list.value = r?.list || []
    pagination.total = r?.total || 0
  } catch {
    list.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const onFilter = () => {
  pagination.page = 1
  fetchList()
}

const clearFilters = () => {
  filter.shareType = ''
  filter.status = ''
  onFilter()
}

const onReveal = async (row: Share) => {
  try {
    await ElMessageBox.confirm(
      '公布后，学员立刻能看到这例的标准结论、病灶和标注。',
      '公布金标准',
      { type: 'warning', confirmButtonText: '公布', cancelButtonText: '再等等' }
    )
  } catch {
    return
  }
  try {
    await TeachingApi.revealShare(row.id)
    ElMessage.success('已向学员公布金标准')
    fetchList()
  } catch {
    /* 已弹错误 */
  }
}

const onRevoke = async (row: Share) => {
  try {
    await ElMessageBox.confirm(
      `确认收回该临时分享？收回后学员端将立即不可见。`,
      '收回分享',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await TeachingApi.revokeShare(row.id)
    ElMessage.success('已收回')
    fetchList()
  } catch {
    /* 已弹错误 */
  }
}

const detailVisible = ref(false)
const detail = ref<Share | null>(null)
const showDetail = (row: Share) => {
  detail.value = row
  detailVisible.value = true
}

const isExpired = (row: Share) => {
  if (row.shareType !== 'TEMPORARY' || row.status !== 'SHARING') return false
  if (!row.expiredAt) return false
  return new Date(row.expiredAt).getTime() < Date.now()
}

const effectiveStatus = (row: Share): TeachingApi.ShareStatus => {
  if (isExpired(row)) return 'EXPIRED'
  return row.status
}

const TEACHING_ACCEPT = [
  '.mp4', '.webm', '.mov', '.m4v', '.avi', '.mkv', '.wmv',
  '.ppt', '.pptx', '.doc', '.docx', '.pdf',
]

const fileKind = (name: string): { fileType: string; resourceType: LearningApi.ResourceType; label: string } => {
  const ext = (name.split('.').pop() || '').toLowerCase()
  if (['mp4', 'webm', 'mov', 'm4v', 'avi', 'mkv', 'wmv'].includes(ext)) {
    return { fileType: 'video', resourceType: 'IMAGE_DEMO', label: '视频' }
  }
  if (['ppt', 'pptx'].includes(ext)) {
    return { fileType: 'ppt', resourceType: 'COURSEWARE', label: 'PPT' }
  }
  if (['doc', 'docx'].includes(ext)) {
    return { fileType: 'word', resourceType: 'COURSEWARE', label: 'Word' }
  }
  if (ext === 'pdf') {
    return { fileType: 'pdf', resourceType: 'COURSEWARE', label: 'PDF' }
  }
  return { fileType: 'link', resourceType: 'COURSEWARE', label: '附件' }
}

const kindLabel = (row: LearningApi.LearningResource) => {
  const known: Record<string, string> = { video: '视频', ppt: 'PPT', word: 'Word', pdf: 'PDF', image: '图片' }
  if (known[row.fileType]) return known[row.fileType]
  return fileKind(row.fileUrl || '').label
}

const materials = ref<LearningApi.LearningResource[]>([])
const materialLoading = ref(false)
const fetchMaterials = async () => {
  materialLoading.value = true
  try {
    const r = await LearningApi.listResources({ onlyMine: true, page: 1, pageSize: 50 })
    materials.value = (r?.list || []).filter((item) => !!item.fileUrl)
  } catch {
    materials.value = []
  } finally {
    materialLoading.value = false
  }
}

const uploadVisible = ref(false)
const uploading = ref(false)
const pickedFile = ref<File | null>(null)
const uploadForm = reactive({ title: '', summary: '' })
const pickedLabel = computed(() => {
  if (!pickedFile.value) return ''
  return `${pickedFile.value.name} · ${fileKind(pickedFile.value.name).label}`
})

const openUpload = () => {
  pickedFile.value = null
  uploadForm.title = ''
  uploadForm.summary = ''
  uploadVisible.value = true
}

const onPickFile = (file: File) => {
  pickedFile.value = file
  if (!uploadForm.title.trim()) {
    uploadForm.title = file.name.replace(/\.[^.]+$/, '')
  }
}

const submitUpload = async () => {
  const title = uploadForm.title.trim()
  if (!title) {
    ElMessage.warning('请填写资料标题')
    return
  }
  if (!pickedFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  const kind = fileKind(pickedFile.value.name)
  uploading.value = true
  try {
    const uploaded = await CommonApi.uploadFile(pickedFile.value, 'learning')
    if (!uploaded?.url) {
      ElMessage.error('文件没有上传成功')
      return
    }
    await LearningApi.createResource({
      title,
      summary: uploadForm.summary.trim(),
      resourceType: kind.resourceType,
      fileUrl: uploaded.url,
      fileType: kind.fileType,
      status: 'PUBLISHED',
    })
    ElMessage.success('已上传，学员可在学习资料中查看')
    uploadVisible.value = false
    fetchMaterials()
  } catch {
    /* 请求层已提示 */
  } finally {
    uploading.value = false
  }
}

const removeMaterial = async (row: LearningApi.LearningResource) => {
  try {
    await ElMessageBox.confirm(`确认删除「${row.title}」？学员将不再看到这份资料。`, '删除资料', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await LearningApi.deleteResource(row.id)
    ElMessage.success('已删除')
    fetchMaterials()
  } catch {
    /* 已弹错误 */
  }
}

onMounted(() => {
  fetchList()
  fetchMaterials()
})
</script>

<template>
  <div class="teaching-share-page">
    <header class="page-head">
      <div class="head-left">
        <h2>我的教学分享</h2>
        <div class="muted">分享病例，或上传视频、PPT、Word 给学员学习</div>
      </div>
      <div class="head-right">
        <el-button type="primary" size="small" :icon="Plus" @click="openUpload">上传资料</el-button>
        <el-select
          v-model="filter.shareType"
          placeholder="类型"
          clearable
          size="small"
          style="width: 130px"
          @change="onFilter"
        >
          <el-option label="临时分享" value="TEMPORARY" />
          <el-option label="入库申请" value="PERMANENT" />
        </el-select>
        <el-select
          v-model="filter.status"
          placeholder="状态"
          clearable
          size="small"
          style="width: 120px"
          @change="onFilter"
        >
          <el-option label="分享中" value="SHARING" />
          <el-option label="已过期" value="EXPIRED" />
          <el-option label="已收回" value="REVOKED" />
          <el-option label="待审核" value="PENDING" />
          <el-option label="已通过" value="APPROVED" />
          <el-option label="已驳回" value="REJECTED" />
          <el-option label="已下架" value="SHELVED" />
        </el-select>
        <el-button size="small" @click="clearFilters">清除</el-button>
        <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
      </div>
    </header>

    <div class="card material-card">
      <div class="card-title">已上传的教学资料</div>
      <div class="muted small card-hint">支持视频、PPT、Word、PDF。发布后学员在「学习资料与笔记」中打开。</div>
      <el-table v-loading="materialLoading" :data="materials" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="格式" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ kindLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="220">
          <template #default="{ row }">
            <div class="case-title">{{ row.title }}</div>
            <div v-if="row.summary" class="muted small">{{ row.summary }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            {{ row.status === 'PUBLISHED' ? '已发布' : row.status === 'DRAFT' ? '草稿' : '已下线' }}
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="上传时间" width="170" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button text type="danger" size="small" @click="removeMaterial(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">还没有上传资料，点击右上角「上传资料」</div>
        </template>
      </el-table>
    </div>

    <div class="card">
      <div class="card-title">病例分享记录</div>
      <el-table v-loading="loading" :data="list" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.shareType === 'TEMPORARY' ? 'warning' : 'primary'" effect="plain">
              {{ row.shareType === 'TEMPORARY' ? '临时分享' : '入库申请' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="病例" min-width="220">
          <template #default="{ row }">
            <div class="case-title">{{ row.desensitizedData?.title || '—' }}</div>
            <div v-if="row.desensitizedData?.teaching_points" class="muted small teach-line">
              {{ row.desensitizedData.teaching_points }}
            </div>
            <div class="muted small">
              {{ row.sourceType === 'SCREENING' ? '筛查' : '实训' }}#{{ row.sourceCaseId }}
              · 影像{{ row.desensitizedData?.image_count ?? row.desensitizedData?.imageCount ?? 0 }}张
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusMap[effectiveStatus(row)]?.type || 'info'">
              {{ statusMap[effectiveStatus(row)]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="有效期 / 审核" min-width="200">
          <template #default="{ row }">
            <template v-if="row.shareType === 'TEMPORARY'">
              <div v-if="row.expiredAt" class="small">
                到期：{{ row.expiredAt }}
              </div>
            </template>
            <template v-else>
              <div v-if="row.reviewedAt" class="small">
                审核于 {{ row.reviewedAt }} <span v-if="row.reviewerName">· {{ row.reviewerName }}</span>
              </div>
              <div v-if="row.reviewComment" class="small muted multiline">
                {{ row.status === 'REJECTED' ? '驳回理由：' : '审核备注：' }}{{ row.reviewComment }}
              </div>
            </template>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170" />
        <el-table-column label="金标准" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.shareType !== 'TEMPORARY'" size="small" type="success" effect="plain">随讲解展示</el-tag>
            <el-tag v-else-if="row.answersRevealed === false" size="small" type="warning">未公布</el-tag>
            <el-tag v-else size="small" type="success" effect="plain">已公布</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" :icon="View" @click="showDetail(row)">查看</el-button>
            <el-button
              v-if="row.shareType === 'TEMPORARY' && row.status === 'SHARING' && !isExpired(row) && row.answersRevealed === false"
              text
              type="warning"
              size="small"
              @click="onReveal(row)"
            >
              公布金标准
            </el-button>
            <el-button
              v-if="row.shareType === 'TEMPORARY' && row.status === 'SHARING' && !isExpired(row)"
              text
              type="danger"
              size="small"
              :icon="RemoveFilled"
              @click="onRevoke(row)"
            >
              收回
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '暂无分享记录' }}</div>
        </template>
      </el-table>

      <div v-if="pagination.total > pagination.pageSize" class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </div>

    <el-dialog v-model="uploadVisible" title="上传教学资料" width="520" destroy-on-close>
      <el-form label-width="72px">
        <el-form-item label="标题" required>
          <el-input v-model="uploadForm.title" maxlength="160" placeholder="例如：眼底阅片课件" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input
            v-model="uploadForm.summary"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="可选，学员在资料列表里会看到"
          />
        </el-form-item>
        <el-form-item label="文件" required>
          <UniversalUploader
            biz="learning"
            variant="dragger"
            :auto-upload="false"
            :accept="TEACHING_ACCEPT"
            hint="点击或拖拽视频、PPT、Word、PDF"
            @select="onPickFile"
          />
          <div v-if="pickedLabel" class="picked">已选择：{{ pickedLabel }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">发布给学员</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="分享详情" width="880">
      <div v-if="detail" class="detail">
        <div class="row">
          <span class="lbl">类型</span>
          <span>{{ detail.shareType === 'TEMPORARY' ? '临时分享' : '入库申请' }}</span>
        </div>
        <div class="row">
          <span class="lbl">状态</span>
          <el-tag size="small" :type="statusMap[effectiveStatus(detail)]?.type || 'info'">
            {{ statusMap[effectiveStatus(detail)]?.label }}
          </el-tag>
        </div>
        <div class="row">
          <span class="lbl">教学标题</span>
          <span>{{ detail.desensitizedData?.title || '—' }}</span>
        </div>
        <TeachingDemoBody :source="detail.desensitizedData" />
        <div class="row">
          <span class="lbl">来源病例</span>
          <span>{{ detail.sourceType === 'SCREENING' ? '筛查' : '实训' }}#{{ detail.sourceCaseId }}</span>
        </div>
        <div class="row" v-if="detail.expiredAt">
          <span class="lbl">到期时间</span>
          <span>{{ detail.expiredAt }}</span>
        </div>
        <div class="row" v-if="detail.reviewComment">
          <span class="lbl">{{ detail.status === 'REJECTED' ? '驳回理由' : '审核备注' }}</span>
          <span class="multiline">{{ detail.reviewComment }}</span>
        </div>
        <div class="row" v-if="detail.reviewedAt">
          <span class="lbl">审核时间</span>
          <span>{{ detail.reviewedAt }}<span v-if="detail.reviewerName"> · {{ detail.reviewerName }}</span></span>
        </div>
        <div class="row">
          <span class="lbl">创建时间</span>
          <span>{{ detail.createdAt }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.teaching-share-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 28px 36px;
  min-height: 100vh;
  background: #ffffff;
}
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 12px;
  flex-wrap: wrap;
}
.head-left h2 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #1d2129; }
.head-left .muted { color: #86909c; font-size: 13px; }
.head-right { display: flex; gap: 8px; align-items: center; }

.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 16px;
}
.card-title { font-size: 15px; font-weight: 600; color: #1d2129; margin-bottom: 4px; }
.card-hint { margin-bottom: 10px; }
.picked { margin-top: 8px; font-size: 12px; color: #1d2129; }
.case-title { color: #1d2129; font-weight: 500; }
.teach-line {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 2px 0;
}
.muted { color: #86909c; font-size: 12px; }
.muted.small { font-size: 11px; }
.small { font-size: 12px; }
.multiline { white-space: pre-wrap; word-break: break-word; }
.empty { padding: 36px 0; text-align: center; color: #c9cdd4; font-size: 14px; }
.pagination { margin-top: 14px; display: flex; justify-content: flex-end; }

.detail .row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
  color: #1d2129;
  border-bottom: 1px dashed #f1f2f5;
}
.detail .row:last-child { border-bottom: none; }
.detail .lbl { width: 90px; flex-shrink: 0; color: #86909c; }
</style>
