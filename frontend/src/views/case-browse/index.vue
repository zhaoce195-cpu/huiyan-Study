<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  View,
  Promotion,
  Share,
  UploadFilled,
  Delete,
  EditPen
} from '@element-plus/icons-vue'
import { CaseBrowseApi, CaseImageApi, PracticeApi, RotationApi } from '@/api'
import type { PageResult } from '@/utils/request'
import { useTrainingJoinStore } from '@/stores/training-join'
import { useUserStore } from '@/stores/user'
import CaseDetailDialog from './components/CaseDetailDialog.vue'
import CaseImagePreview from './components/CaseImagePreview.vue'
import CaseImageUploadDialog from './components/CaseImageUploadDialog.vue'
import GoldStandardDialog from './components/GoldStandardDialog.vue'
import CaseBatchImportDialog from './components/CaseBatchImportDialog.vue'
import ShareDialog from '@/views/training/components/ShareDialog.vue'
import DynamicFilter from '@/components/DynamicFilter.vue'
import { CASE_BROWSE_FILTER } from '@/utils/filter-presets'

type Item = CaseBrowseApi.CaseBrowseItem
type Detail = CaseBrowseApi.CaseBrowseDetail

const router = useRouter()
const route = useRoute()
const joinStore = useTrainingJoinStore()
const userStore = useUserStore()

/* ========== 角色 ========== */

const canArchive = computed(() => userStore.canManage)
const browseFilter = computed(() => {
  if (canArchive.value) return CASE_BROWSE_FILTER
  return {
    ...CASE_BROWSE_FILTER,
    fields: CASE_BROWSE_FILTER.fields.map((field) =>
      field.key === 'keyword'
        ? { ...field, label: '编号 / case_sn / 标题' }
        : field
    )
  }
})
const importDialogRef = ref<InstanceType<typeof CaseBatchImportDialog> | null>(null)

/* ========== 列表与筛选 ========== */

const list = ref<Item[]>([])
const total = ref(0)
const loading = ref(false)

const filter = reactive<CaseBrowseApi.CaseBrowseQuery>({
  keyword: '',
  category: '',
  drLevel: '',
  difficulty: '',
  archiveStatus: '',
  creatorRole: '',
  startTime: '',
  endTime: '',
  onlyIncomplete: false
})

const pagination = reactive({ page: 1, pageSize: 20 })

const fetchList = async () => {
  loading.value = true
  try {
    const params: CaseBrowseApi.CaseBrowseQuery = {
      ...filter,
      page: pagination.page,
      pageSize: pagination.pageSize
    }
    const res = (await CaseBrowseApi.getCaseBrowseList(params)) as PageResult<Item>
    list.value = res?.list || []
    total.value = res?.total || 0
    // 以后端权威 isTrainCase 同步本地 store，避免刷新后状态漂移
    list.value.forEach((row) => {
      if (row.isTrainCase) joinStore.markJoined(row.id)
      else joinStore.unmarkJoined(row.id)
    })
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.page = 1
  fetchList()
}

const onReset = () => {
  filter.keyword = ''
  filter.category = ''
  filter.drLevel = ''
  filter.difficulty = ''
  filter.archiveStatus = ''
  filter.creatorRole = ''
  filter.onlyIncomplete = false
  filter.startTime = ''
  filter.endTime = ''
  pagination.page = 1
  fetchList()
}

/* ========== 详情弹窗 ========== */

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<Detail | null>(null)

const openDetail = async (row: Item) => {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    detailData.value = await CaseBrowseApi.getCaseBrowseDetail(row.id)
  } catch {
    detailData.value = null
  } finally {
    detailLoading.value = false
  }
}

const openVisit = (id: number) => {
  openDetail({ id } as Item)
}

const onSubjectSaved = (detail: Detail) => {
  detailData.value = detail
  fetchList()
}

/* ========== 影像预览 ========== */

const previewVisible = ref(false)
const previewImages = ref<string[]>([])
const previewIndex = ref(0)

const openPreview = (row: Item) => {
  detailLoading.value = true
  CaseBrowseApi.getCaseBrowseDetail(row.id)
    .then((d) => {
      const imgs = (d?.images || []).filter(Boolean)
      if (imgs.length === 0) {
        ElMessage.info('该病例暂无影像')
        return
      }
      previewImages.value = imgs
      previewIndex.value = 0
      previewVisible.value = true
    })
    .catch(() => {
      ElMessage.error('影像加载失败')
    })
    .finally(() => {
      detailLoading.value = false
    })
}

/* ========== 加入实训 ==========
 * 权限：仅 TEACHER / ADMIN（canArchive=true）可调用；学员侧按钮整体隐藏。
 * 后端：POST /case-browse/{caseId}/join-training
 *  - 200：is_train_case 置为 true
 *  - 403：当前角色无权
 *  - 404：病例不存在
 *  - 400：病例已归档
 * 反馈：
 *  - 已加入   → ElMessage.info「该病例已在实训库中，无需重复添加」
 *  - 加入成功 → ElMessage.success「病例已成功加入实训，学员可在自主练习中使用」
 *  - 加入失败 → ElMessage.error「加入实训失败，请稍后重试」
 */
const joinTraining = async (row: Item) => {
  // 0) 学员前端二次拦截（后端仍会再校验）
  if (!canArchive.value) {
    ElMessage.warning('当前角色无权操作病例实训状态')
    return
  }
  // 1) 归档病例直接拦截
  if (row.archiveStatus === 'ARCHIVED') {
    ElMessage.warning('该病例已归档，无法加入实训')
    return
  }
  // 2) 已加入：以数据库字段为准，不再看本地缓存
  if (row.isTrainCase) {
    ElMessage.info('该病例已在实训库中，无需重复添加')
    return
  }
  // 3) 防重复点击：loading 中直接返回
  if (joinStore.isJoining(row.id)) return

  joinStore.setJoining(row.id, true)
  try {
    const res = await CaseBrowseApi.joinTrainingCase(row.id)
    const detail = res.detail
    if (!detail || detail.isTrainCase !== true) {
      ElMessage.error('加入实训没有写入数据库，请稍后重试')
      return
    }
    row.isTrainCase = true
    row.isPublished = detail.isPublished
    joinStore.markJoined(row.id)
    if (detailData.value?.id === row.id) {
      detailData.value = { ...detailData.value, isTrainCase: true, isPublished: detail.isPublished }
    }
    ElMessage.success('病例已成功加入实训，学员可在自主练习中使用')
  } catch (err: any) {
    const status = err?.response?.status
    const msg: string = err?.message || ''

    if (status === 403) {
      ElMessage.error('当前角色无权将病例加入实训')
    } else if (
      status === 409 ||
      /已加入|已存在|已在实训|already|duplicate/i.test(msg)
    ) {
      // 兼容未来后端返回的「重复」语义
      joinStore.markJoined(row.id)
      row.isTrainCase = true
      ElMessage.info('该病例已在实训库中，无需重复添加')
    } else {
      ElMessage.error('加入实训失败，请稍后重试')
    }
  } finally {
    joinStore.setJoining(row.id, false)
  }
}

const inTraining = (row: { isTrainCase?: boolean }) => !!row.isTrainCase

const leaveTraining = async (row: Item) => {
  if (!canArchive.value) {
    ElMessage.warning('当前角色无权操作病例实训状态')
    return
  }
  if (joinStore.isJoining(row.id)) return
  try {
    await ElMessageBox.confirm(
      '取消后会写入数据库：学员不能再练习这例，今日学习里的这项必做也会去掉。',
      '取消加入实训',
      { type: 'warning', confirmButtonText: '取消加入', cancelButtonText: '保留' }
    )
  } catch {
    return
  }
  joinStore.setJoining(row.id, true)
  try {
    const detail = await CaseBrowseApi.leaveTrainingCase(row.id)
    if (!detail || detail.isTrainCase !== false) {
      ElMessage.error('取消没有写入数据库，请稍后重试')
      return
    }
    row.isTrainCase = false
    joinStore.unmarkJoined(row.id)
    if (detailData.value?.id === row.id) {
      detailData.value = { ...detailData.value, isTrainCase: false }
    }
    ElMessage.success('已取消加入实训，学员练习和今日任务里都不再出现这例')
  } catch (err: any) {
    const status = err?.response?.status
    if (status === 403) ElMessage.error('当前角色无权取消加入实训')
    else ElMessage.error('取消加入实训失败，请稍后重试')
  } finally {
    joinStore.setJoining(row.id, false)
  }
}

/* ========== 影像阅片 ========== */

const goReading = (row: Item) => {
  if (!row?.id) {
    ElMessage.error('病例 ID 缺失，无法进入阅片')
    return
  }
  if (row.archiveStatus === 'ARCHIVED') {
    ElMessage.warning('该病例已归档，无法进入阅片')
    return
  }
  if (row.imageCount === 0) {
    ElMessage.info('该病例暂无影像')
    return
  }
  router.push({ path: '/training/reading', query: { caseId: String(row.id) } })
}

const studyingId = ref(0)
const openCase = async (row: Item) => {
  if (canArchive.value) {
    goReading(row)
    return
  }
  if (!row?.id) return
  if (row.archiveStatus === 'ARCHIVED') {
    ElMessage.warning('该病例已归档')
    return
  }
  if (row.imageCount === 0) {
    ElMessage.info('这例没有眼底照')
    return
  }
  studyingId.value = row.id
  try {
    const rec = await PracticeApi.startPractice({ caseId: row.id, mode: 'SELECTED' })
    router.push({
      path: '/training/practice/workstation',
      query: { sessionId: String(rec.id), caseId: String(row.id) }
    })
  } finally {
    studyingId.value = 0
  }
}

/* ========== 补传影像 ========== */
const uploadDialogVisible = ref(false)
const uploadDialogCaseId = ref<number>(0)
const uploadDialogMissing = ref<CaseImageApi.CaseImageRole[]>([])
const uploadDialogDefaultRole = ref<CaseImageApi.CaseImageRole>('original')
const openImageUpload = (row: Item) => {
  if (!row?.id) {
    ElMessage.error('病例 ID 缺失')
    return
  }
  uploadDialogCaseId.value = row.id
  uploadDialogMissing.value = (row.missingRoles || []) as CaseImageApi.CaseImageRole[]
  uploadDialogDefaultRole.value = (uploadDialogMissing.value[0] as CaseImageApi.CaseImageRole) || 'original'
  uploadDialogVisible.value = true
}
const onImageUploaded = () => {
  fetchList()
}

/* ========== 归档 ========== */

const onArchiveToggle = async (row: Item) => {
  const target: CaseBrowseApi.ArchiveStatus =
    row.archiveStatus === 'ARCHIVED' ? 'ACTIVE' : 'ARCHIVED'
  const verb = target === 'ARCHIVED' ? '归档' : '恢复'

  try {
    await ElMessageBox.confirm(
      `确定${verb}病例「${row.caseNo} · ${row.title || '-'}」吗？`,
      '操作确认',
      { type: 'warning', confirmButtonText: `确定${verb}`, cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  try {
    await CaseBrowseApi.archiveCase(row.id, { archiveStatus: target })
    fetchList()
  } catch {
    /* 已弹错误提示 */
  }
}

/* ========== 批量勾选 / 批量删除（追加，不影响现有单行操作） ==========
 * 行为：对每个勾选项依次调用现有的 archiveCase（软删 → ARCHIVED）。
 * 仅医生 / 管理员可见；与单行「归档 / 恢复」保持完全一致语义，避免引入新接口。
 */
const selectedRows = ref<Item[]>([])
const batchDeleting = ref(false)

const onSelectionChange = (rows: Item[]) => {
  selectedRows.value = rows
}


const onBatchDelete = async () => {
  if (!canArchive.value) {
    ElMessage.warning('当前角色无权批量删除病例')
    return
  }
  const rows = selectedRows.value.filter((r) => r.archiveStatus !== 'ARCHIVED')
  if (rows.length === 0) {
    ElMessage.info('已勾选病例均为已归档，无需重复处理')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定批量删除已勾选的 ${rows.length} 条病例？此操作会将其归档，不影响阅片 / 实训 / 患者已确认报告。`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  batchDeleting.value = true
  let okCnt = 0
  const failed: { id: number; reason: string }[] = []
  for (const row of rows) {
    try {
      await CaseBrowseApi.archiveCase(row.id, { archiveStatus: 'ARCHIVED' })
      okCnt += 1
    } catch (e: any) {
      failed.push({ id: row.id, reason: e?.message || '未知错误' })
    }
  }
  batchDeleting.value = false
  selectedRows.value = []
  if (failed.length === 0) {
    ElMessage.success(`批量删除完成：成功 ${okCnt} 条`)
  } else {
    ElMessage.warning(`批量删除完成：成功 ${okCnt} 条，失败 ${failed.length} 条`)
  }
  fetchList()
}

/* ========== Tag 颜色 ========== */
const archiveTagType = (s: CaseBrowseApi.ArchiveStatus) =>
  s === 'ARCHIVED' ? 'info' : 'success'

const drTagType = (level: number) => {
  if (level >= 4) return 'danger'
  if (level >= 3) return 'warning'
  if (level >= 1) return 'primary'
  return 'success'
}

const difficultyTagType = (d: string) => {
  if (d === 'HARD') return 'danger'
  if (d === 'MEDIUM') return 'warning'
  return 'success'
}

const creatorRoleText = (r: string) => {
  if (r === 'ADMIN') return '管理员'
  if (r === 'TEACHER') return '带教医师'
  if (r === 'STUDENT') return '住培医师'
  return r || '—'
}


onMounted(() => {
  if (route.query?.onlyIncomplete === '1' || route.query?.onlyIncomplete === 'true') {
    filter.onlyIncomplete = true
  }
  const kw = route.query?.keyword
  if (typeof kw === 'string' && kw.trim()) {
    filter.keyword = kw.trim()
  }
  fetchList()
})

/* ========== 完善 / 修订金标准 ========== */

const goldVisible = ref(false)
const goldData = ref<Detail | null>(null)

const canEditGold = (row: Item | Detail) => {
  if (!canArchive.value) return false
  if (row.archiveStatus === 'ARCHIVED') return false
  if (userStore.isAdmin) return true
  return Number(row.creatorId) === Number(userStore.userInfo.id)
}

const openGold = async (row: { id: number }) => {
  try {
    const detail = await CaseBrowseApi.getCaseBrowseDetail(row.id)
    if (!canEditGold(detail)) {
      ElMessage.warning('仅可修订本人创建的病例金标准')
      return
    }
    goldData.value = detail
    goldVisible.value = true
  } catch {
    ElMessage.error('无法打开金标准编辑')
  }
}

const onGoldSaved = async (detail: Detail) => {
  const row = list.value.find((r) => r.id === detail.id)
  const wasTrain = !!(row?.isPublished && row?.isTrainCase)
  if (row) {
    row.isPublished = detail.isPublished
    row.isTrainCase = detail.isTrainCase
    row.drLevel = detail.drLevel
    row.drGradeText = detail.drGradeText
    if (detail.isTrainCase) joinStore.markJoined(row.id)
    else joinStore.unmarkJoined(row.id)
  }
  if (detailData.value?.id === detail.id) {
    detailData.value = detail
  }
  if (!canArchive.value || wasTrain || !detail.isPublished || !detail.isTrainCase) return
  try {
    await ElMessageBox.confirm(
      '这份病例已经可以给学员练习。要放进当前轮转的必做里吗？学员首页会看到这项任务。',
      '加入本轮转',
      { confirmButtonText: '加入', cancelButtonText: '暂不' }
    )
    await RotationApi.addTask({ kind: 'CASE', caseId: detail.id })
    ElMessage.success('已加入本轮转，学员今日学习里能看到')
  } catch {
    /* 取消，或该病例已经在轮转里 */
  }
}

const consumeGoldQuery = async (raw: unknown) => {
  const id = Number(raw)
  if (!id) return
  await openGold({ id })
  const next = { ...route.query }
  delete next.goldCaseId
  router.replace({ path: route.path, query: next })
}

watch(
  () => route.query.goldCaseId,
  (v) => {
    if (v) consumeGoldQuery(v)
  },
  { immediate: true }
)

/* ========== 教学分享 ========== */
const canShare = computed(() => userStore.isAdmin || userStore.isDoctor)
const shareDialogVisible = ref(false)
const shareDialogType = ref<'TEMPORARY' | 'PERMANENT'>('TEMPORARY')
const shareDialogCase = ref<{ id: number; title: string } | null>(null)

const onShareTemp = (row: Item) => {
  shareDialogType.value = 'TEMPORARY'
  shareDialogCase.value = { id: row.id, title: row.title || row.caseNo || '' }
  shareDialogVisible.value = true
}

const onShareSubmit = (row: Item) => {
  shareDialogType.value = 'PERMANENT'
  shareDialogCase.value = { id: row.id, title: row.title || row.caseNo || '' }
  shareDialogVisible.value = true
}
</script>

<template>
  <div class="case-browse-page">
    <main class="page-main">
      <!-- 筛选区 -->
      <section class="card filter-card">
        <DynamicFilter
          v-model="filter"
          :schema="browseFilter"
          :loading="loading"
          @submit="onSearch"
          @reset="onReset"
          @refresh="fetchList"
        />
        <div v-if="canArchive" class="filter-extra">
          <el-button @click="importDialogRef?.open()">批量导入</el-button>
          <el-button
            type="danger"
            :icon="Delete"
            :disabled="selectedRows.length === 0"
            :loading="batchDeleting"
            @click="onBatchDelete"
          >
            批量删除<span v-if="selectedRows.length > 0">（{{ selectedRows.length }}）</span>
          </el-button>
        </div>
      </section>

      <!-- 列表区 -->
      <section class="card list-card">
        <el-table
          v-loading="loading"
          :data="list"
          size="default"
          stripe
          row-key="id"
          empty-text="暂无符合条件的病例，请调整检索条件"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="46" :selectable="(row: Item) => row.archiveStatus !== 'ARCHIVED'" />
          <el-table-column type="index" label="#" width="56" />
          <el-table-column label="病例编号" width="180">
            <template #default="{ row }">
              <div class="case-no">{{ row.caseNo }}</div>
              <div v-if="row.caseSn" class="case-sn">{{ row.caseSn }}</div>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="220">
            <template #default="{ row }">
              <div class="case-title">{{ row.title || '—' }}</div>
              <div v-if="row.description" class="case-desc">{{ row.description }}</div>
            </template>
          </el-table-column>
          <el-table-column v-if="canArchive" label="患者信息" width="190">
            <template #default="{ row }">
              <div class="patient-line">
                <b class="p-name">{{ row.patientName || '—' }}</b>
                <el-tag
                  v-if="row.patientGender === 'M'"
                  size="small"
                  type="primary"
                  effect="plain"
                  style="margin-left: 4px"
                >男</el-tag>
                <el-tag
                  v-else-if="row.patientGender === 'F'"
                  size="small"
                  type="danger"
                  effect="plain"
                  style="margin-left: 4px"
                >女</el-tag>
                <span v-if="row.patientAge" class="muted small p-age">{{ row.patientAge }} 岁</span>
              </div>
              <div v-if="row.patientPhone" class="muted small">
                {{ row.patientPhone }}
              </div>
              <div v-else-if="!row.phoneVisible" class="muted small">
                ——（无权限）
              </div>
            </template>
          </el-table-column>
          <el-table-column label="病种" width="180">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.categoryText || row.category }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="DR 等级" width="160">
            <template #default="{ row }">
              <el-tag
                v-if="row.drLevel !== null && row.drLevel !== undefined"
                size="small"
                :type="drTagType(row.drLevel)"
                effect="plain"
              >
                {{ row.drGradeText || `${row.drLevel} 级` }}
              </el-tag>
              <span v-else class="blinded-hint">作答后可见</span>
            </template>
          </el-table-column>
          <el-table-column label="难度" width="92">
            <template #default="{ row }">
              <el-tag size="small" :type="difficultyTagType(row.difficulty)">
                {{ row.difficultyText || row.difficulty }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="资料" width="180" align="center">
            <template #default="{ row }">
              <div>
                <span class="muted">眼底照相 {{ row.imageCount }} 张</span>
                <span v-if="canArchive && row.derivedCount" class="muted derived">
                  · 标注层 {{ row.derivedCount }} 项
                </span>
              </div>
              <el-tag
                v-if="!row.imageCount"
                size="small"
                type="warning"
                effect="dark"
                style="margin-top: 2px"
              >
                没有眼底照
              </el-tag>
              <span v-else-if="row.fundusOnly !== false" class="muted small">无其他资料</span>
            </template>
          </el-table-column>
          <el-table-column label="检查" width="160">
            <template #default="{ row }">
              <template v-if="(row.visitCount || 1) > 1">
                <div>同一病人 第 {{ row.visitIndex || 1 }} / {{ row.visitCount }} 次</div>
                <span class="muted small">{{ row.examOn || '检查日期未提供' }}</span>
              </template>
              <template v-else>
                <div>单次图像</div>
                <span class="muted small">没有其他时期</span>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="140">
            <template #default="{ row }">
              <el-tag size="small" :type="archiveTagType(row.archiveStatus)" effect="plain">
                {{ row.archiveStatus === 'ARCHIVED' ? '已归档' : '在用' }}
              </el-tag>
              <el-tag
                v-if="!row.isPublished"
                size="small"
                type="warning"
                effect="plain"
                style="margin-left: 4px"
              >
                草稿
              </el-tag>
              <el-tag
                v-else-if="row.isTrainCase"
                size="small"
                type="success"
                effect="dark"
                style="margin-left: 4px"
              >
                实训
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建人" width="160">
            <template #default="{ row }">
              <div>{{ row.creatorName || '—' }}</div>
              <div class="muted small">{{ creatorRoleText(row.creatorRole) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="170">
            <template #default="{ row }">
              <span class="muted small">{{ row.createdAt || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="500" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" :icon="View" @click="openDetail(row)">详情</el-button>
              <el-button
                v-if="canEditGold(row)"
                text
                type="warning"
                size="small"
                :icon="EditPen"
                @click="openGold(row)"
              >
                {{ row.isPublished ? '修订金标准' : '完善金标准' }}
              </el-button>
              <el-tooltip
                v-if="row.imageCount === 0"
                content="该病例暂无眼底图，请先补传后再阅片"
                placement="top"
              >
                <el-button
                  text
                  type="info"
                  size="small"
                  disabled
                >
                  请补充眼底图
                </el-button>
              </el-tooltip>
              <el-button
                v-else
                text
                type="warning"
                size="small"
                :loading="studyingId === row.id"
                @click="openCase(row)"
              >
                {{ canArchive ? `阅片（${row.imageCount} 张）` : '学习这例' }}
              </el-button>
              <el-button
                text
                type="info"
                size="small"
                :disabled="row.imageCount === 0"
                @click="openPreview(row)"
              >
                看图
              </el-button>
              <el-button
                v-if="canArchive"
                text
                size="small"
                type="primary"
                :icon="UploadFilled"
                @click="openImageUpload(row)"
              >
                补传影像
              </el-button>
              <!-- 归档 / 恢复：后端与处理函数一直都在，只是从未接上按钮，
                   导致这个功能全系统没有任何入口（遗留清单 D-008） -->
              <el-button
                v-if="canArchive"
                text
                size="small"
                :type="row.archiveStatus === 'ARCHIVED' ? 'success' : 'danger'"
                @click="onArchiveToggle(row)"
              >
                {{ row.archiveStatus === 'ARCHIVED' ? '恢复' : '归档' }}
              </el-button>
              <el-button
                v-if="canArchive"
                text
                size="small"
                :type="inTraining(row) ? 'warning' : 'success'"
                :icon="inTraining(row) ? Delete : Promotion"
                :loading="joinStore.isJoining(row.id)"
                :disabled="
                  joinStore.isJoining(row.id) ||
                  (!inTraining(row) && row.archiveStatus === 'ARCHIVED')
                "
                @click="inTraining(row) ? leaveTraining(row) : joinTraining(row)"
              >
                {{ inTraining(row) ? '取消加入实训' : '加入实训' }}
              </el-button>
              <el-button
                v-if="canShare && row.archiveStatus !== 'ARCHIVED'"
                text
                size="small"
                type="primary"
                :icon="Share"
                @click="onShareTemp(row)"
              >
                分享实训
              </el-button>
              <el-button
                v-if="canShare && row.archiveStatus !== 'ARCHIVED'"
                text
                size="small"
                type="warning"
                :icon="Promotion"
                @click="onShareSubmit(row)"
              >
                转为教学
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="total > 0" class="pagination">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            background
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="fetchList"
            @current-change="fetchList"
          />
        </div>
      </section>
    </main>

    <!-- 详情弹窗 -->
    <CaseDetailDialog
      v-model:visible="detailVisible"
      :loading="detailLoading"
      :data="detailData"
      :can-archive="canArchive"
      @open-visit="openVisit"
      @subject-saved="onSubjectSaved"
      :can-edit-gold="!!detailData && canEditGold(detailData)"
      @join-training="(row: Detail) => joinTraining(row as Item)"
      @leave-training="(row: Detail) => leaveTraining(row as Item)"
      @edit-gold="(row: Detail) => openGold(row)"
      @preview-images="(imgs: string[]) => {
        previewImages = imgs
        previewIndex = 0
        previewVisible = true
      }"
    />

    <CaseBatchImportDialog ref="importDialogRef" @imported="fetchList" />

    <GoldStandardDialog
      v-model:visible="goldVisible"
      :data="goldData"
      @saved="onGoldSaved"
    />

    <!-- 影像预览 -->
    <CaseImagePreview
      v-model:visible="previewVisible"
      :images="previewImages"
      :initial-index="previewIndex"
    />

    <!-- 补传 / 追加影像（医生 / 管理员） -->
    <CaseImageUploadDialog
      v-model:visible="uploadDialogVisible"
      case-table="training"
      :case-id="uploadDialogCaseId"
      :default-role="uploadDialogDefaultRole"
      :missing-roles="uploadDialogMissing"
      @saved="onImageUploaded"
    />

    <!-- 教学分享 / 入库（医生 / 管理员） -->
    <ShareDialog
      v-if="shareDialogCase"
      v-model:visible="shareDialogVisible"
      :share-type="shareDialogType"
      source-type="TRAINING"
      :source-case-id="shareDialogCase.id"
      :case-title="shareDialogCase.title"
    />
  </div>
</template>

<style scoped>
.derived {
  color: #7cc4ff;
}

/* 盲训态占位：答案型字段在作答前不展示 */
.blinded-hint {
  color: #909399;
  font-size: 12px;
}

.case-browse-page {
  min-height: 100vh;
  background: #f5f6fa;
  display: flex;
  flex-direction: column;
}

.page-header {
  height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e5e6eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.divider {
  width: 1px;
  height: 18px;
  background: #e5e6eb;
}
.page-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}

.page-main {
  flex: 1;
  max-width: none;
  width: 100%;
  margin: 0 auto;
  padding: 20px 24px;
  box-sizing: border-box;
}

.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 18px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.filter-grid > :last-child {
  grid-column: span 2;
}
.filter-actions {
  margin-top: 14px;
  display: flex;
  gap: 8px;
}
.filter-extra {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.case-no {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #1677ff;
  font-weight: 600;
}
.case-sn {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #86909c;
  font-size: 11px;
  margin-top: 2px;
}
.patient-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}
.p-name {
  color: #1d2129;
  font-size: 13px;
}
.p-age {
  margin-left: 4px;
}
.case-title {
  font-weight: 500;
  color: #1d2129;
}
.case-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #86909c;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.muted {
  color: #86909c;
  font-size: 13px;
}
.muted.small {
  font-size: 12px;
}

.pagination {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1100px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filter-grid > :last-child {
    grid-column: span 2;
  }
}
</style>
