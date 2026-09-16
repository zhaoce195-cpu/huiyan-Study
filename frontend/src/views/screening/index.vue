<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox
} from 'element-plus'
import {
  Back,
  Refresh,
  Document,
  DataAnalysis,
  View,
  Download,
  Printer,
  Promotion,
  Iphone,
  Edit,
  Delete,
  RemoveFilled,
  CircleCheck
} from '@element-plus/icons-vue'
import { ScreeningApi, LoginApi, PatientApi } from '@/api'
import { useCaseBindingStore } from '@/stores/case-binding'
import { useUserStore } from '@/stores/user'
import CaseEditDialog from './components/CaseEditDialog.vue'
import DiagnosisUpload from './components/DiagnosisUpload.vue'
import DynamicFilter from '@/components/DynamicFilter.vue'
import { SCREENING_QUEUE_FILTER } from '@/utils/filter-presets'

type RiskLevel = ScreeningApi.RiskLevel
type Status = ScreeningApi.ScreeningStatus
type Eye = ScreeningApi.EyeSide
type Task = ScreeningApi.ScreeningTask
type FrontRole = LoginApi.FrontRole

const router = useRouter()
const goBack = () => router.push('/')
const bindingStore = useCaseBindingStore()
const userStore = useUserStore()

/* ================== 角色 / 权限 ================== */

const currentRole = computed<FrontRole | ''>(() => userStore.role)
const currentUserName = computed<string>(
  () => userStore.userInfo.name || userStore.userInfo.username || ''
)
const currentHospital = computed<string>(() => userStore.userInfo.hospital || '')

const isStudent = computed(() => currentRole.value === 'trainee')
const isTeacher = computed(() => currentRole.value === 'doctor')
const isAdmin = computed(() => currentRole.value === 'admin')
/** 写权限：上传 / 删除 / 重新分析 / 转诊 — 仅 医师 / 管理员 */
const canManage = computed(() => userStore.canManage)

const roleTagText = computed(() =>
  isStudent.value
    ? '只读模式 · 学员'
    : isTeacher.value
      ? '医师工作台'
      : isAdmin.value
        ? '管理员工作台'
        : '只读模式'
)
const roleTagType = computed<'success' | 'warning' | 'danger' | 'info'>(() =>
  isAdmin.value ? 'danger' : isTeacher.value ? 'warning' : isStudent.value ? 'success' : 'info'
)

/* ================== 状态 ================== */

const tasks = ref<Task[]>([])
const listLoading = ref(false)

const filter = reactive({
  keyword: '',
  risk: '' as RiskLevel | '',
  status: '' as Status | '',
  diagnosisType: '' as 'MA' | 'DR' | 'COMPREHENSIVE' | '',
})

const pagination = reactive({
  page: 1,
  pageSize: 50,
  total: 0
})

const stats = ref<ScreeningApi.ScreeningStats>({
  total: 0,
  red: 0,
  yellow: 0,
  green: 0,
  pending: 0,
  failed: 0,
  todayCount: 0,
  weekCount: 0
})

/* ================== 计算属性 ================== */

const riskWeight: Record<string, number> = { red: 0, yellow: 1, green: 2 }
const statusWeight: Record<Status, number> = {
  analyzing: 0,
  queued: 1,
  done: 2,
  failed: 3
}

const filteredTasks = computed(() => {
  return [...tasks.value].sort((a, b) => {
    const ra = a.risk ? riskWeight[a.risk] : 99
    const rb = b.risk ? riskWeight[b.risk] : 99
    if (ra !== rb) return ra - rb
    return statusWeight[a.status] - statusWeight[b.status]
  })
})

const localStats = computed(() => {
  const total = stats.value.total || tasks.value.length
  const red = stats.value.red || tasks.value.filter((t) => t.risk === 'red').length
  const yellow = stats.value.yellow || tasks.value.filter((t) => t.risk === 'yellow').length
  const green = stats.value.green || tasks.value.filter((t) => t.risk === 'green').length
  const pending =
    stats.value.pending ||
    tasks.value.filter((t) => t.status === 'queued' || t.status === 'analyzing').length
  return { total, red, yellow, green, pending }
})

const statusMap: Record<Status, { text: string; type: string }> = {
  queued: { text: '排队中', type: 'info' },
  analyzing: { text: '处理中', type: 'warning' },
  done: { text: '已完成', type: 'success' },
  failed: { text: '失败', type: 'danger' }
}
const riskTextMap: Record<RiskLevel, string> = {
  red: '高危 · 建议转诊',
  yellow: '中危 · 建议随访',
  green: '正常'
}
const eyeMap: Record<Eye, { label: string; type: 'primary' | 'success' | 'warning' }> = {
  OD: { label: 'OD 右眼', type: 'primary' },
  OS: { label: 'OS 左眼', type: 'success' },
  OU: { label: 'OU 双眼', type: 'warning' }
}

/* ================== Mock 兜底（后端未就绪时使用） ================== */

const mockTasks: Task[] = [
  {
    id: 'T2026001', patientId: 'P2026001', patientName: '王建国', eye: 'OU', age: 64, gender: '男',
    status: 'done', risk: 'red', dr: '4 级 PDR（增殖性）', confidence: 0.974,
    createdAt: '2026-05-21 08:42:15', fileName: 'P2026001_OU.jpg',
    hospital: '北京同仁医院体检中心', doctor: '张敏',
    remark: '糖尿病史 12 年，建议尽快眼底激光治疗'
  },
  {
    id: 'T2026002', patientId: 'P2026002', patientName: '李秀兰', eye: 'OS', age: 58, gender: '女',
    status: 'done', risk: 'red', dr: '3 级 重度 NPDR', confidence: 0.961,
    createdAt: '2026-05-21 08:55:32', fileName: 'P2026002_OS.jpg',
    hospital: '北京同仁医院体检中心', doctor: '张敏',
    remark: '伴黄斑水肿，建议 2 周内眼科专科就诊'
  },
  {
    id: 'T2026003', patientId: 'P2026003', patientName: '陈志强', eye: 'OD', age: 47, gender: '男',
    status: 'done', risk: 'yellow', dr: '2 级 中度 NPDR', confidence: 0.913,
    createdAt: '2026-05-21 09:10:18', fileName: 'P2026003_OD.jpg',
    hospital: '上海瑞金医院体检中心', doctor: '刘文涛',
    remark: '建议 3 个月内复查眼底'
  },
  {
    id: 'T2026004', patientId: 'P2026004', patientName: '赵丽华', eye: 'OU', age: 51, gender: '女',
    status: 'done', risk: 'yellow', dr: '1 级 轻度 NPDR', confidence: 0.882,
    createdAt: '2026-05-21 09:24:07', fileName: 'P2026004_OU.jpg',
    hospital: '上海瑞金医院体检中心', doctor: '刘文涛',
    remark: '微动脉瘤少量，6 个月随访'
  },
  {
    id: 'T2026005', patientId: 'P2026005', patientName: '孙德海', eye: 'OD', age: 39, gender: '男',
    status: 'done', risk: 'green', dr: '0 级 正常', confidence: 0.992,
    createdAt: '2026-05-21 09:31:42', fileName: 'P2026005_OD.jpg',
    hospital: '广州中山眼科中心', doctor: '吴佳',
    remark: '眼底未见异常，建议每年常规筛查'
  },
  {
    id: 'T2026006', patientId: 'P2026006', patientName: '周玉梅', eye: 'OS', age: 35, gender: '女',
    status: 'analyzing', risk: null, dr: '—', confidence: 0,
    createdAt: '2026-05-21 09:38:51', fileName: 'P2026006_OS.jpg',
    hospital: '广州中山眼科中心', doctor: '吴佳',
    remark: 'AI 模型分析中（约 5 秒）'
  },
  {
    id: 'T2026007', patientId: 'P2026007', patientName: '吴明辉', eye: 'OU', age: 44, gender: '男',
    status: 'queued', risk: null, dr: '—', confidence: 0,
    createdAt: '2026-05-21 09:42:09', fileName: 'P2026007_OU.jpg',
    hospital: '深圳市眼科医院', doctor: '林晓东',
    remark: '排队中，前面 2 个任务'
  },
  {
    id: 'T2026008', patientId: 'P2026008', patientName: '钱国栋', eye: 'OD', age: 67, gender: '男',
    status: 'failed', risk: null, dr: '—', confidence: 0,
    createdAt: '2026-05-21 09:45:23', fileName: 'P2026008_OD.jpg',
    hospital: '深圳市眼科医院', doctor: '林晓东',
    remark: '图像质量过低（曝光不足），请重新拍摄'
  }
]
const usingMock = ref(false)
const fallbackToMock = (reason: string) => {
  if (usingMock.value) return
  usingMock.value = true
  tasks.value = mockTasks
  pagination.total = mockTasks.length
  ElMessage.warning(`后端未就绪（${reason}），已使用本地演示数据`)
}

/* ================== 接口对接 ================== */

const fetchList = async (silent = false) => {
  if (!silent) listLoading.value = true
  try {
    const query: ScreeningApi.ScreeningQuery = {
      keyword: filter.keyword || undefined,
      risk: filter.risk || undefined,
      status: filter.status || undefined,
      diagnosisType: filter.diagnosisType || undefined,
      page: pagination.page,
      pageSize: pagination.pageSize,
      sortBy: 'risk',
      sortOrder: 'asc',
      // 「分析任务队列」视图：仅排队中 / 处理中 / 失败
      scope: 'queue'
    }
    const prevIds = new Set(tasks.value.map((t) => t.id))
    const res = await ScreeningApi.getScreeningList(query)
    if (res && Array.isArray(res.list)) {
      // 应用本地绑定 overlay
      const next = res.list.map((row) => bindingStore.applyOverlay(row))
      // 检测「自动归档」：上一轮还在 / 这一轮消失 → 已完成被归档
      if (silent && prevIds.size > 0) {
        const nextIds = new Set(next.map((t) => t.id))
        const archivedCount = [...prevIds].filter((id) => !nextIds.has(id)).length
        if (archivedCount > 0) {
          ElMessage({
            message: `已完成 ${archivedCount} 条任务，已自动归档至病例检索`,
            type: 'success',
            duration: 2200,
            grouping: true
          })
        }
      }
      tasks.value = next
      pagination.total = res.total ?? res.list.length
      usingMock.value = false
    } else {
      fallbackToMock('返回数据为空')
    }
  } catch (e: any) {
    fallbackToMock(e?.message || '接口异常')
  } finally {
    listLoading.value = false
  }
}

const fetchStats = async () => {
  try {
    // 「分析任务队列」头部统计：仅统计队列中未完成任务
    const res = await ScreeningApi.getScreeningStats('queue')
    if (res) stats.value = res
  } catch {
    /* 静默：localStats 会兜底 */
  }
}

const refreshList = () => {
  fetchList()
  fetchStats()
  ElMessage.success('队列已刷新')
}

const onFilterChange = () => {
  pagination.page = 1
  fetchList()
}

/** CSU-EYES 诊断完成 → 列表 + 统计同步刷新 */
const onDiagnosisDone = (_payload: any) => {
  fetchList()
  fetchStats()
}

/* ================== 上传 ==================
 * 上传能力已抽成 DiagnosisUpload 组件（含拖拽），本页只负责挂载。
 * 抽离时旧的处理函数与状态变量留在了这里成为孤儿，
 * 已随类型检查清理一并移除。
 */





const walkEntry = (entry: any, out: File[]): Promise<void> =>
  new Promise((resolve) => {
    if (entry.isFile) {
      entry.file((f: File) => {
        out.push(f)
        resolve()
      })
    } else if (entry.isDirectory) {
      const reader = entry.createReader()
      reader.readEntries((entries: any[]) => {
        Promise.all(entries.map((e) => walkEntry(e, out))).then(() => resolve())
      })
    } else resolve()
  })


/* ================== 报告预览 / 导出 ================== */

const previewTask = ref<Task | null>(null)
const previewVisible = ref(false)
const previewLoading = ref(false)
const reportDetail = ref<ScreeningApi.ScreeningReport | null>(null)

const showReport = async (t: Task) => {
  previewTask.value = t
  previewVisible.value = true
  previewLoading.value = true
  reportDetail.value = null
  try {
    const r = await ScreeningApi.getScreeningReport(t.id)
    if (r) reportDetail.value = r
  } catch {
    /* 后端未就绪时使用 task 本身渲染 */
  } finally {
    previewLoading.value = false
  }
}

const exportingMap = ref<Record<string, boolean>>({})
const exportPdf = async (t: Task) => {
  exportingMap.value[t.id] = true
  try {
    await ScreeningApi.exportReportPdf(
      t.id,
      `${t.patientId}_${t.patientName}_DR筛查报告.pdf`
    )
    ElMessage.success(`【${t.patientId} ${t.patientName}】报告 PDF 导出完成`)
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败，请联系管理员')
  } finally {
    exportingMap.value[t.id] = false
  }
}

const summaryExporting = ref(false)
const exportAll = async () => {
  summaryExporting.value = true
  try {
    await ScreeningApi.exportSummaryPdf(
      {
        keyword: filter.keyword || undefined,
        risk: filter.risk || undefined,
        status: filter.status || undefined
      },
      `DR筛查汇总报告_${Date.now()}.pdf`
    )
    ElMessage.success('已生成今日筛查汇总报告（PDF）')
  } catch (e: any) {
    ElMessage.error(e?.message || '汇总报告导出失败')
  } finally {
    summaryExporting.value = false
  }
}

/* ================== 操作 ================== */

/* ---------- 病患手机号绑定 ---------- */
const bindPhoneVisible = ref(false)
const bindPhoneTask = ref<Task | null>(null)
const bindPhoneInput = ref('')
const bindPhoneSaving = ref(false)
const phoneRegBind = /^1[3-9]\d{9}$/

const openBindPhone = (t: Task) => {
  bindPhoneTask.value = t
  bindPhoneInput.value = t.patientPhone || ''
  bindPhoneVisible.value = true
}

const submitBindPhone = async () => {
  if (!bindPhoneTask.value) return
  const phone = (bindPhoneInput.value || '').trim()
  if (phone && !phoneRegBind.test(phone)) {
    ElMessage.warning('请输入 11 位有效手机号（或留空清除绑定）')
    return
  }
  bindPhoneSaving.value = true
  try {
    if (!bindPhoneTask.value.caseId) {
      ElMessage.warning('无法获取病例数据库 ID，无法绑定')
      return
    }
    await PatientApi.bindCasePhone(bindPhoneTask.value.caseId, phone)
    if (phone) {
      bindingStore.setBinding(
        {
          caseId: bindPhoneTask.value.caseId,
          patientId: bindPhoneTask.value.patientId,
        },
        phone,
        true,
      )
    } else {
      bindingStore.clearBinding({
        caseId: bindPhoneTask.value.caseId,
        patientId: bindPhoneTask.value.patientId,
      })
    }
    bindPhoneVisible.value = false
    fetchList()
  } catch {
    /* error already shown */
  } finally {
    bindPhoneSaving.value = false
  }
}

/* ---------- 确认报告（同步至病患账号） ---------- */
const confirmingMap = ref<Record<string, boolean>>({})
const confirmReport = async (t: Task) => {
  if (!canManage.value) {
    ElMessage.warning('当前角色无权确认报告')
    return
  }
  if (t.status !== 'done') {
    ElMessage.info('仅 AI 已分析完成的病例可确认')
    return
  }
  if (t.confirmed) {
    ElMessage.info('该病例已确认，无需重复操作')
    return
  }
  if (!t.patientPhone) {
    try {
      await ElMessageBox.confirm(
        '该病例尚未绑定病患手机号，确认报告后无法推送至病患账号。\n是否立即绑定手机号？',
        '需要先绑定手机号',
        {
          type: 'warning',
          confirmButtonText: '去绑定',
          cancelButtonText: '取消'
        }
      )
      openBindPhone(t)
    } catch {
      /* 用户取消 */
    }
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认将「${t.patientName || t.id}」的报告标记为「已确认」？\n` +
        `系统将自动同步至手机号 ${t.patientPhone} 对应的病患账号。`,
      '医师确认报告',
      {
        type: 'warning',
        confirmButtonText: '确认',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }
  confirmingMap.value[t.id] = true
  try {
    const res = await ScreeningApi.confirmReport({ taskId: t.id })
    t.confirmed = true
    ElMessage.success(
      res.patientBound
        ? `已确认并同步至病患账号（${res.patientPhone}）`
        : '已确认。该病例尚未绑定病患账号，病患侧暂不可见。'
    )
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '确认失败')
  } finally {
    confirmingMap.value[t.id] = false
  }
}

/* ---------- 编辑 / 补充病例（仅医生 / 管理员） ---------- */
const editVisible = ref(false)
const editTask = ref<Task | null>(null)
const openEdit = (t: Task) => {
  if (!canManage.value) {
    ElMessage.warning('当前角色无权编辑病例')
    return
  }
  if (!t.caseId) {
    ElMessage.warning('该病例缺少数据库 ID，无法编辑')
    return
  }
  editTask.value = { ...t }
  editVisible.value = true
}
const onCaseSaved = () => {
  fetchList()
  fetchStats()
}

const removeTask = async (t: Task) => {
  if (!canManage.value) {
    ElMessage.warning('只读模式不可移除任务')
    return
  }
  try {
    await ElMessageBox.confirm(`确定移除 ${t.patientId} 的分析记录？`, '提示', {
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await ScreeningApi.deleteScreeningTask(t.id)
    tasks.value = tasks.value.filter((x) => x.id !== t.id)
    tasks.value = tasks.value.filter((x) => x.id !== t.id)
    fetchStats()
  } catch (e: any) {
    // 后端未就绪：本地删除以保持交互
    tasks.value = tasks.value.filter((x) => x.id !== t.id)
    if (!usingMock.value) ElMessage.error(e?.message || '删除失败')
  }
}

/* ---------- 批量勾选 / 批量删除 / 批量移出队列 ---------- */
const selectedTasks = ref<Task[]>([])
const batchLoading = ref(false)

const onSelectionChange = (rows: Task[]) => {
  selectedTasks.value = rows
}

const clearSelection = () => {
  selectedTasks.value = []
}

const batchDeleteTasks = async () => {
  if (!canManage.value) {
    ElMessage.warning('只读模式不可批量删除')
    return
  }
  if (selectedTasks.value.length === 0) {
    ElMessage.info('请先勾选要删除的任务')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定批量删除已勾选的 ${selectedTasks.value.length} 条任务？此操作不可恢复。`,
      '批量删除确认',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }
  batchLoading.value = true
  try {
    const ids = selectedTasks.value.map((t) => t.id)
    const res = await ScreeningApi.batchDeleteScreeningTasks(ids)
    const idSet = new Set(ids.filter((i) => !res.failedIds?.includes(i)))
    tasks.value = tasks.value.filter((x) => !idSet.has(x.id))
    selectedTasks.value = []
    fetchStats()
    if (res.failedCount > 0) {
      ElMessage.warning(
        `批量删除完成：成功 ${res.successCount} 条，失败 ${res.failedCount} 条`
      )
    }
  } catch (e: any) {
    if (!usingMock.value) ElMessage.error(e?.message || '批量删除失败')
  } finally {
    batchLoading.value = false
  }
}

const batchRemoveFromQueue = async () => {
  if (!canManage.value) {
    ElMessage.warning('只读模式不可批量移出队列')
    return
  }
  if (selectedTasks.value.length === 0) {
    ElMessage.info('请先勾选要移出队列的任务')
    return
  }
  // 只对仍在队列中的任务有效
  const queueRows = selectedTasks.value.filter(
    (t) => t.status === 'queued' || t.status === 'analyzing' || t.status === 'failed'
  )
  if (queueRows.length === 0) {
    ElMessage.info('已勾选的任务均不在队列中（已完成 / 已复核）')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定将已勾选的 ${queueRows.length} 条任务移出分析队列？` +
        (selectedTasks.value.length > queueRows.length
          ? `\n（其余 ${selectedTasks.value.length - queueRows.length} 条已完成，不在队列中，将被跳过）`
          : ''),
      '批量移出队列确认',
      {
        type: 'warning',
        confirmButtonText: '确认移出',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }
  batchLoading.value = true
  try {
    const ids = selectedTasks.value.map((t) => t.id)
    const res = await ScreeningApi.batchRemoveFromQueue(ids)
    const failedSet = new Set(res.failedIds || [])
    // 仅本地剔除真正被移出（状态符合且未失败）的行；跳过的保留
    const removed = queueRows
      .filter((t) => !failedSet.has(t.id))
      .map((t) => t.id)
    const removedSet = new Set(removed)
    tasks.value = tasks.value.filter((x) => !removedSet.has(x.id))
    selectedTasks.value = []
    fetchStats()
    if (res.failedCount > 0 || res.skippedCount > 0) {
      ElMessage.warning(
        `批量移出完成：成功 ${res.successCount} 条` +
          (res.skippedCount ? `，跳过 ${res.skippedCount} 条` : '') +
          (res.failedCount ? `，失败 ${res.failedCount} 条` : '')
      )
    }
  } catch (e: any) {
    if (!usingMock.value) ElMessage.error(e?.message || '批量移出失败')
  } finally {
    batchLoading.value = false
  }
}

const reanalyzing = ref<Record<string, boolean>>({})
const reanalyze = async (t: Task) => {
  if (!canManage.value) {
    ElMessage.warning('只读模式不可重新分析')
    return
  }
  reanalyzing.value[t.id] = true
  // 先在本地切换为分析中，体验更流畅
  t.status = 'analyzing'
  t.risk = null
  t.dr = '—'
  t.confidence = 0
  t.remark = 'AI 模型分析中…'
  try {
    const fresh = await ScreeningApi.reanalyzeTask({ taskId: t.id, force: true })
    if (fresh) Object.assign(t, fresh)
    setTimeout(() => fetchList(true), 1500)
  } catch (e: any) {
    if (!usingMock.value) ElMessage.error(e?.message || '重新分析失败')
  } finally {
    reanalyzing.value[t.id] = false
  }
}

/* ================== 高危转诊 ================== */

const referVisible = ref(false)
const referLoading = ref(false)
const referTask = ref<Task | null>(null)
const referForm = reactive({
  targetHospital: '',
  note: ''
})
const referHospitalOptions = [
  '北京同仁医院 · 眼科中心',
  '上海瑞金医院 · 眼科',
  '广州中山眼科中心',
  '深圳市眼科医院',
  '复旦大学附属眼耳鼻喉科医院',
  '温州医科大学附属眼视光医院'
]

const openRefer = (t: Task) => {
  if (!canManage.value) {
    ElMessage.warning('只读模式不可发起转诊申请')
    return
  }
  if (t.risk !== 'red') {
    ElMessage.info('仅高危（红色）病例可一键转诊')
    return
  }
  referTask.value = t
  referForm.targetHospital = ''
  referForm.note = `${t.patientId} ${t.patientName}（${t.age}岁/${t.gender}）AI 分级 ${t.dr}，置信度 ${(t.confidence * 100).toFixed(1)}%。${t.remark || ''}`.trim()
  referVisible.value = true
}

const submitRefer = async () => {
  if (!referTask.value) return
  if (!referForm.targetHospital) {
    ElMessage.warning('请选择转诊目标机构')
    return
  }
  referLoading.value = true
  try {
    await ScreeningApi.referHighRisk(
      referTask.value.id,
      referForm.targetHospital,
      referForm.note || undefined
    )
    referVisible.value = false
  } catch (e: any) {
    if (!usingMock.value) ElMessage.error(e?.message || '转诊申请提交失败')
    else {
      ElMessage.success('演示模式：已模拟提交转诊申请')
      referVisible.value = false
    }
  } finally {
    referLoading.value = false
  }
}

/* ================== 生命周期 ================== */

/** 队列轮询：分析完成的任务会因 scope=queue 过滤而消失 */
const POLL_INTERVAL_MS = 8000
let pollTimer: ReturnType<typeof setInterval> | null = null
const startPoll = () => {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    fetchList(true)
    fetchStats()
  }, POLL_INTERVAL_MS)
}
const stopPoll = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  fetchStats()
  fetchList()
  startPoll()
})

// 从病例检索页或其他位置完成绑定后，再回到本页要刷新一次以同步最新状态
onActivated(() => {
  fetchStats()
  fetchList(true)
  startPoll()
})

onDeactivated(stopPoll)
onBeforeUnmount(stopPoll)
</script>

<template>
  <div class="screening">
    <header class="topbar">
      <div class="left">
        <el-button text :icon="Back" @click="goBack">返回首页</el-button>
        <div class="divider"></div>
        <div class="title">
          <span class="dot blue"></span>
          体检筛查端 · DR AI 辅助分级
        </div>
      </div>
      <div class="right">
        <el-tag v-if="currentUserName" type="info" size="small" effect="plain">
          {{ currentUserName }}{{ currentHospital ? ' · ' + currentHospital : '' }}
        </el-tag>
        <el-tag :type="roleTagType" size="small" effect="dark">
          {{ roleTagText }}
        </el-tag>
        <el-tag type="primary" size="small">三甲质控标准</el-tag>
        <el-button
          :icon="Download"
          type="primary"
          :loading="summaryExporting"
          @click="exportAll"
        >
          导出汇总报告
        </el-button>
      </div>
    </header>

    <section class="stats">
      <div class="stat-card">
        <div class="stat-icon blue"><el-icon><DataAnalysis /></el-icon></div>
        <div class="stat-info">
          <div class="num">{{ localStats.total }}</div>
          <div class="label">累计筛查</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon red">●</div>
        <div class="stat-info">
          <div class="num red-text">{{ localStats.red }}</div>
          <div class="label">高危 · 转诊</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon yellow">●</div>
        <div class="stat-info">
          <div class="num yellow-text">{{ localStats.yellow }}</div>
          <div class="label">中危 · 随访</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon green">●</div>
        <div class="stat-info">
          <div class="num green-text">{{ localStats.green }}</div>
          <div class="label">正常</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon gray"><el-icon><Refresh /></el-icon></div>
        <div class="stat-info">
          <div class="num">{{ localStats.pending }}</div>
          <div class="label">分析中 / 排队</div>
        </div>
      </div>
    </section>

    <!-- 智能诊断三选一（替代原批量上传） -->
    <DiagnosisUpload
      class="upload-card"
      :can-diagnose="canManage"
      @done="onDiagnosisDone"
    />

    <section class="task-card">
      <div class="task-header">
        <div class="task-title">
          <el-icon><Document /></el-icon>
          分析任务队列
          <span class="count">{{ pagination.total || filteredTasks.length }}</span>
        </div>
        <div class="task-filter">
          <DynamicFilter
            v-model="filter"
            :schema="SCREENING_QUEUE_FILTER"
            :show-actions="false"
            @submit="onFilterChange"
            @refresh="refreshList"
          />
          <el-button :icon="Refresh" @click="refreshList">刷新</el-button>
        </div>
      </div>

      <!-- 批量操作条（仅医生 / 管理员，且已勾选时显示；不破坏现有布局） -->
      <div
        v-if="canManage && selectedTasks.length > 0"
        class="batch-bar"
      >
        <span class="batch-info">已勾选 {{ selectedTasks.length }} 条</span>
        <el-button
          type="warning"
          size="small"
          :icon="RemoveFilled"
          :loading="batchLoading"
          @click="batchRemoveFromQueue"
        >
          批量移出队列
        </el-button>
        <el-button
          type="danger"
          size="small"
          :icon="Delete"
          :loading="batchLoading"
          v-show="false"
          @click="batchDeleteTasks"
        >
          批量删除
        </el-button>
        <el-button size="small" text @click="clearSelection">取消选择</el-button>
      </div>

      <el-table
        v-loading="listLoading"
        element-loading-text="正在加载筛查任务…"
        :data="filteredTasks"
        stripe
        size="default"
        style="width: 100%"
        :row-class-name="(o: any) => o.row.risk ? 'risk-row-' + o.row.risk : ''"
        @selection-change="onSelectionChange"
      >
        <el-table-column
          v-if="canManage"
          type="selection"
          width="48"
          :selectable="() => true"
        />
        <el-table-column type="index" label="#" width="56" />
        <el-table-column prop="patientId" label="患者ID" width="110" />
        <el-table-column prop="patientName" label="姓名" width="90" />
        <el-table-column label="性别 / 年龄" width="110">
          <template #default="{ row }">{{ row.gender }} / {{ row.age }}</template>
        </el-table-column>
        <el-table-column label="眼别" width="100">
          <template #default="{ row }">
            <el-tag :type="eyeMap[row.eye as Eye].type" size="small" effect="plain">
              {{ eyeMap[row.eye as Eye].label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag
              :type="(statusMap[row.status as Status]?.type as any)"
              size="small"
              effect="dark"
            >
              {{ statusMap[row.status as Status]?.text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="160">
          <template #default="{ row }">
            <span v-if="!row.risk" class="muted">—</span>
            <span v-else :class="['hy-risk-tag', 'hy-risk-' + row.risk]">
              {{ riskTextMap[row.risk as RiskLevel] }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="dr" label="DR 分级" width="170" />
        <el-table-column label="智能诊断" width="180">
          <template #default="{ row }">
            <div v-if="row.diagnosisType" class="diag-cell">
              <el-tag
                :type="row.diagnosisType === 'MA' ? '' : row.diagnosisType === 'DR' ? 'warning' : 'success'"
                size="small"
                effect="dark"
              >
                {{ row.diagnosisType === 'MA' ? 'MA' : row.diagnosisType === 'DR' ? 'DR' : '综合' }}
              </el-tag>
              <span class="diag-summary">{{ row.diagnosisSummary }}</span>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="120">
          <template #default="{ row }">
            <span v-if="row.confidence">
              <el-progress
                :percentage="Number((row.confidence * 100).toFixed(1))"
                :stroke-width="6"
                :show-text="false"
                style="width: 60px; display: inline-block; vertical-align: middle"
              />
              <span class="conf-num">{{ (row.confidence * 100).toFixed(1) }}%</span>
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="hospital" label="送检机构" min-width="180" show-overflow-tooltip />
        <el-table-column prop="doctor" label="送检医师" width="100" />
        <el-table-column prop="createdAt" label="提交时间" min-width="160" />
        <el-table-column label="操作" width="460" fixed="right">
          <template #default="{ row }">
            <el-button
              text
              type="primary"
              :icon="View"
              :disabled="row.status !== 'done'"
              @click="showReport(row)"
            >
              查看报告
            </el-button>
            <el-button
              text
              type="success"
              :icon="Printer"
              :disabled="row.status !== 'done'"
              :loading="!!exportingMap[row.id]"
              @click="exportPdf(row)"
            >
              导出PDF
            </el-button>
            <el-button
              v-if="canManage"
              text
              type="warning"
              :icon="Refresh"
              :disabled="row.status === 'analyzing'"
              :loading="!!reanalyzing[row.id]"
              @click="reanalyze(row)"
            >
              重新分析
            </el-button>
            <el-button
              v-if="canManage && row.status === 'done'"
              text
              type="warning"
              :icon="CircleCheck"
              :disabled="!!row.confirmed"
              :loading="!!confirmingMap[row.id]"
              @click="confirmReport(row)"
            >
              {{ row.confirmed ? '已确认' : '确认报告' }}
            </el-button>
            <el-button
              v-if="canManage && row.risk === 'red' && row.status === 'done'"
              text
              type="danger"
              :icon="Promotion"
              @click="openRefer(row)"
            >
              一键转诊
            </el-button>
            <el-button
              v-if="canManage && !row.patientPhone"
              text
              type="primary"
              :icon="Iphone"
              @click="openBindPhone(row)"
            >
              绑定手机号
            </el-button>
            <el-tag
              v-else-if="canManage && row.patientPhone"
              type="success"
              size="small"
              effect="plain"
              class="bound-tag"
            >
              已关联
            </el-tag>
            <el-button
              v-if="canManage"
              text
              type="info"
              :icon="Edit"
              @click="openEdit(row)"
            >
              编辑/补充
            </el-button>
            <el-button
              v-if="canManage"
              text
              type="danger"
              @click="removeTask(row)"
            >
              移除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">
            {{ listLoading ? '加载中…' : '暂无分析任务，请上传眼底图' }}
          </div>
        </template>
      </el-table>

      <div class="pagination" v-if="pagination.total > pagination.pageSize">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[20, 50, 100, 200]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchList()"
          @current-change="fetchList()"
        />
      </div>
    </section>

    <el-dialog
      v-model="previewVisible"
      title="DR 筛查报告预览"
      width="720"
      :close-on-click-modal="false"
    >
      <div v-loading="previewLoading" element-loading-text="正在加载报告…">
        <div v-if="previewTask" class="report">
          <div class="report-head">
            <div class="report-title">
              糖尿病视网膜病变 AI 筛查报告
              <div class="report-sub">
                慧眼医疗云平台 V2.0 · 报告编号
                {{ reportDetail?.reportNo || previewTask.id }}
              </div>
            </div>
            <div :class="['hy-risk-tag', 'hy-risk-' + (previewTask.risk || 'green')]">
              {{ previewTask.risk ? riskTextMap[previewTask.risk] : '正常' }}
            </div>
          </div>
          <el-descriptions :column="2" border size="small" class="report-desc">
            <el-descriptions-item label="患者ID">{{ previewTask.patientId }}</el-descriptions-item>
            <el-descriptions-item label="姓名">{{ previewTask.patientName }}</el-descriptions-item>
            <el-descriptions-item label="性别">{{ previewTask.gender }}</el-descriptions-item>
            <el-descriptions-item label="年龄">{{ previewTask.age }} 岁</el-descriptions-item>
            <el-descriptions-item label="眼别">
              {{ eyeMap[previewTask.eye].label }}
            </el-descriptions-item>
            <el-descriptions-item label="检查时间">{{ previewTask.createdAt }}</el-descriptions-item>
            <el-descriptions-item label="送检机构">{{ previewTask.hospital }}</el-descriptions-item>
            <el-descriptions-item label="送检医师">{{ previewTask.doctor }}</el-descriptions-item>
            <el-descriptions-item label="DR 分级">{{ previewTask.dr }}</el-descriptions-item>
            <el-descriptions-item label="AI 置信度">
              {{ (previewTask.confidence * 100).toFixed(1) }}%
            </el-descriptions-item>
          </el-descriptions>
          <div class="report-conclusion">
            <div class="ck-title">AI 辅助诊断意见</div>
            <p v-if="reportDetail?.conclusion">{{ reportDetail.conclusion }}</p>
            <template v-else>
              <p v-if="previewTask.risk === 'red'">
                检测到 <b>显著糖尿病视网膜病变</b> 征象（{{ previewTask.dr }}），{{ previewTask.remark }}。
              </p>
              <p v-else-if="previewTask.risk === 'yellow'">
                检测到 <b>{{ previewTask.dr }}</b> 征象，{{ previewTask.remark }}。
              </p>
              <p v-else>
                未检测到明显糖尿病视网膜病变征象。{{ previewTask.remark }}。
              </p>
            </template>
            <p v-if="reportDetail?.suggestion" class="suggestion">
              <b>建议处置：</b>{{ reportDetail.suggestion }}
            </p>
          </div>
          <div class="report-tip">
            ⚠ 本结果仅供医师辅助参考，最终诊断须由具备资质的医师作出。
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
        <el-button
          v-if="canManage && previewTask?.status === 'done' && !previewTask.confirmed"
          type="warning"
          :icon="CircleCheck"
          :loading="previewTask ? !!confirmingMap[previewTask.id] : false"
          @click="previewTask && confirmReport(previewTask)"
        >
          确认报告
        </el-button>
        <el-button
          v-if="canManage && previewTask?.risk === 'red'"
          type="danger"
          :icon="Promotion"
          @click="previewTask && openRefer(previewTask)"
        >
          一键转诊
        </el-button>
        <el-button
          type="primary"
          :icon="Download"
          :loading="previewTask ? !!exportingMap[previewTask.id] : false"
          @click="previewTask && exportPdf(previewTask)"
        >
          导出 PDF
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="referVisible"
      title="高危病例 · 一键转诊申请"
      width="540"
      :close-on-click-modal="false"
    >
      <div v-if="referTask" class="refer-info">
        <div class="refer-row">
          <span class="lbl">患者信息</span>
          <span class="val">
            {{ referTask.patientId }} · {{ referTask.patientName }} ·
            {{ referTask.gender }} / {{ referTask.age }}岁 ·
            {{ eyeMap[referTask.eye].label }}
          </span>
        </div>
        <div class="refer-row">
          <span class="lbl">AI 分级</span>
          <span class="val">
            <span class="hy-risk-tag hy-risk-red">{{ riskTextMap.red }}</span>
            <span style="margin-left: 8px">{{ referTask.dr }}</span>
            <span class="conf-num">置信度 {{ (referTask.confidence * 100).toFixed(1) }}%</span>
          </span>
        </div>
        <div class="refer-row">
          <span class="lbl">送检机构</span>
          <span class="val">{{ referTask.hospital }} · {{ referTask.doctor }}</span>
        </div>
      </div>
      <el-form :model="referForm" label-width="100px" size="default">
        <el-form-item label="转诊目标" required>
          <el-select
            v-model="referForm.targetHospital"
            placeholder="请选择目标三甲眼科"
            filterable
            allow-create
            style="width: 100%"
          >
            <el-option
              v-for="h in referHospitalOptions"
              :key="h"
              :label="h"
              :value="h"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="转诊说明">
          <el-input
            v-model="referForm.note"
            type="textarea"
            :rows="3"
            placeholder="可补充病史、既往就诊、紧急程度等"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="referVisible = false">取消</el-button>
        <el-button
          type="danger"
          :icon="Promotion"
          :loading="referLoading"
          @click="submitRefer"
        >
          提交转诊申请
        </el-button>
      </template>
    </el-dialog>

    <!-- 病患手机号绑定弹窗 -->
    <el-dialog v-model="bindPhoneVisible" width="420px" title="绑定病患手机号" destroy-on-close>
      <div class="bind-tip" v-if="bindPhoneTask">
        将病例
        <strong>{{ bindPhoneTask.id }}</strong>
        （{{ bindPhoneTask.patientName }}）绑定至病患账号手机号，
        绑定后该病患登录后可在【我的体检报告】查看本报告。
      </div>
      <el-input
        v-model="bindPhoneInput"
        placeholder="请输入 11 位手机号（留空可清除绑定）"
        maxlength="11"
        :prefix-icon="Iphone"
        clearable
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="bindPhoneVisible = false">取消</el-button>
        <el-button type="primary" :loading="bindPhoneSaving" @click="submitBindPhone">
          确定绑定
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑 / 补充病例弹窗（仅医生 / 管理员） -->
    <CaseEditDialog
      v-model:visible="editVisible"
      :task="editTask"
      @saved="onCaseSaved"
    />
  </div>
</template>

<style scoped>
.screening {
  background: var(--hy-light-bg);
  min-height: 100vh;
  padding: 0 24px 32px;
}

.topbar {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 5;
  background: rgba(245, 247, 250, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #e5e6eb;
  margin: 0 -24px 20px;
  padding: 0 24px;
}
.left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.divider {
  width: 1px;
  height: 18px;
  background: #d8dde5;
}
.title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  letter-spacing: 0.6px;
}
.title .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.title .dot.blue {
  background: #1677ff;
  box-shadow: 0 0 0 4px rgba(22, 119, 255, 0.18);
}
.right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stat-icon.blue { background: #eef4ff; color: #1677ff; }
.stat-icon.red { background: var(--hy-risk-red-bg); color: var(--hy-risk-red); }
.stat-icon.yellow { background: var(--hy-risk-yellow-bg); color: var(--hy-risk-yellow); }
.stat-icon.green { background: var(--hy-risk-green-bg); color: var(--hy-risk-green); }
.stat-icon.gray { background: #f2f3f5; color: #86909c; }
.stat-info .num {
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1.2;
}
.stat-info .label {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.red-text { color: var(--hy-risk-red); }
.yellow-text { color: var(--hy-risk-yellow); }
.green-text { color: var(--hy-risk-green); }

.upload-card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 20px;
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 20px;
  margin-bottom: 20px;
}
.drop-content {
  padding: 36px 20px;
  text-align: center;
}
.drop-title {
  margin: 12px 0 6px;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}
.drop-sub {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 14px;
}

.up-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: #4e5969;
}
.up-current {
  max-width: 70%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.up-num {
  color: #1677ff;
  font-weight: 600;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #4e5969;
}
.tip-no {
  display: inline-block;
  min-width: 26px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  background: #eef4ff;
  color: #1677ff;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.task-card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 18px 20px;
}
.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 12px;
}
.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}
.task-title .count {
  display: inline-block;
  min-width: 28px;
  height: 22px;
  line-height: 22px;
  padding: 0 8px;
  background: #eef4ff;
  color: #1677ff;
  border-radius: 11px;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
}
.task-filter {
  display: flex;
  align-items: center;
  gap: 10px;
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 10px;
  padding: 8px 12px;
  background: #fff7e6;
  border: 1px solid #ffe1a8;
  border-radius: 8px;
}
.batch-info {
  font-size: 13px;
  color: #d46b08;
  font-weight: 600;
  margin-right: 4px;
}

:deep(.risk-row-red) td:nth-child(7) {
  background: rgba(245, 63, 63, 0.04) !important;
}
:deep(.risk-row-yellow) td:nth-child(7) {
  background: rgba(255, 125, 0, 0.05) !important;
}
:deep(.risk-row-green) td:nth-child(7) {
  background: rgba(0, 180, 42, 0.05) !important;
}
/* 启用批量勾选时多了一列，风险标签列向后挪一格，沿用原色 */
:deep(.el-table__row.risk-row-red) td.el-table-column--selection ~ td:nth-child(8) {
  background: rgba(245, 63, 63, 0.04) !important;
}
:deep(.el-table__row.risk-row-yellow) td.el-table-column--selection ~ td:nth-child(8) {
  background: rgba(255, 125, 0, 0.05) !important;
}
:deep(.el-table__row.risk-row-green) td.el-table-column--selection ~ td:nth-child(8) {
  background: rgba(0, 180, 42, 0.05) !important;
}
.conf-num {
  margin-left: 6px;
  font-size: 12px;
  color: #4e5969;
  vertical-align: middle;
}

.muted { color: #c9cdd4; }

.diag-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.diag-summary {
  font-size: 12px;
  color: #4e5969;
  margin-top: 2px;
}
.bound-tag {
  margin: 0 6px;
  vertical-align: middle;
}
.empty {
  padding: 36px 0;
  color: #c9cdd4;
  font-size: 14px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.report-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 16px;
}
.report-title {
  font-size: 18px;
  font-weight: 700;
  color: #1d2129;
}
.report-sub {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
  font-weight: 400;
}
.report-desc {
  margin-bottom: 16px;
}
.report-conclusion {
  background: #f7faff;
  border: 1px solid #e0eafc;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.7;
}
.ck-title {
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 6px;
}
.suggestion {
  margin-top: 8px;
}
.report-tip {
  margin-top: 14px;
  font-size: 12px;
  color: var(--hy-risk-yellow);
}

.refer-info {
  background: #fff7f7;
  border: 1px solid #fde2e2;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.7;
}
.refer-row {
  display: flex;
  gap: 12px;
}
.refer-row .lbl {
  flex: 0 0 76px;
  color: #86909c;
}
.refer-row .val {
  flex: 1;
  color: #1d2129;
}
</style>
