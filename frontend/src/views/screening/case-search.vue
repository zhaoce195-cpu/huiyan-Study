<script setup lang="ts">
/**
 * 体检筛查端 · 病例检索（独立页面）
 * - 支持：上传时间区间 / 病例编号 / 患者姓名 / 手机号
 * - 列表：患者ID 姓名 手机号 风险等级 上传时间 状态
 * - 操作：查看报告 / 导出PDF / 绑定手机号 / 确认报告 / 移除
 */
import { computed, onActivated, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search,
  Refresh,
  RefreshLeft,
  View,
  Printer,
  Iphone,
  CircleCheck,
  Delete,
  Download,
  Edit
} from '@element-plus/icons-vue'
import { ScreeningApi, LoginApi, PatientApi } from '@/api'
import { useCaseBindingStore } from '@/stores/case-binding'
import { useUserStore } from '@/stores/user'
import CaseEditDialog from './components/CaseEditDialog.vue'
import DynamicFilter from '@/components/DynamicFilter.vue'
import { SCREENING_ARCHIVE_FILTER } from '@/utils/filter-presets'

type Task = ScreeningApi.ScreeningTask
type Status = ScreeningApi.ScreeningStatus
type RiskLevel = ScreeningApi.RiskLevel
type Eye = ScreeningApi.EyeSide
type FrontRole = LoginApi.FrontRole

const router = useRouter()
const bindingStore = useCaseBindingStore()
const userStore = useUserStore()

/* ===== 角色权限 ===== */
const currentRole = computed<FrontRole | ''>(() => userStore.role)
const canManage = computed(() => userStore.canManage)

/* ===== 检索条件 ===== */
const filter = reactive<Record<string, any>>({
  startTime: '',
  endTime: '',
  caseNo: '',
  patientName: '',
  phone: '',
  risk: '' as RiskLevel | '',
  status: '' as Status | '',
  diagnosisType: '' as 'MA' | 'DR' | 'COMPREHENSIVE' | '',
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const tasks = ref<Task[]>([])
const listLoading = ref(false)

const buildQuery = (): ScreeningApi.ScreeningQuery => ({
  caseNo: filter.caseNo.trim() || undefined,
  patientName: filter.patientName.trim() || undefined,
  phone: filter.phone.trim() || undefined,
  startTime: filter.startTime || undefined,
  endTime: filter.endTime || undefined,
  risk: filter.risk || undefined,
  status: filter.status || undefined,
  diagnosisType: filter.diagnosisType || undefined,
  page: pagination.page,
  pageSize: pagination.pageSize,
  sortBy: 'createdAt',
  sortOrder: 'desc',
  // 「病例检索」视图：仅已完成 / 已复核 病例
  scope: 'archive'
})

const fetchList = async () => {
  listLoading.value = true
  try {
    const res = await ScreeningApi.getScreeningList(buildQuery())
    const list = res?.list || []
    // 应用本地绑定 overlay：保证另一个列表里刚发生的绑定立刻生效
    tasks.value = list.map((row) => bindingStore.applyOverlay(row))
    pagination.total = res?.total ?? tasks.value.length
  } catch (e: any) {
    ElMessage.error(e?.message || '加载病例列表失败')
    tasks.value = []
    pagination.total = 0
  } finally {
    listLoading.value = false
  }
}

const onSearch = () => {
  pagination.page = 1
  fetchList()
}

const onReset = () => {
  filter.startTime = ''
  filter.endTime = ''
  filter.caseNo = ''
  filter.patientName = ''
  filter.phone = ''
  filter.risk = ''
  filter.status = ''
  filter.diagnosisType = ''
  pagination.page = 1
  fetchList()
}

const onRefresh = () => {
  fetchList()
  ElMessage.success('列表已刷新')
}

/* ===== 视图字典 ===== */
const statusMap: Record<Status, { text: string; type: string }> = {
  queued: { text: '排队中', type: 'info' },
  analyzing: { text: '处理中', type: 'warning' },
  done: { text: '已完成', type: 'success' },
  failed: { text: '失败', type: 'danger' }
}
const riskTextMap: Record<RiskLevel, string> = {
  red: '高危',
  yellow: '中危',
  green: '正常'
}
const eyeMap: Record<Eye, string> = { OD: 'OD 右眼', OS: 'OS 左眼', OU: 'OU 双眼' }

/* ===== 报告预览 ===== */
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewTask = ref<Task | null>(null)
const reportDetail = ref<ScreeningApi.ScreeningReport | null>(null)

const showReport = async (t: Task) => {
  if (t.status !== 'done') {
    ElMessage.info('该病例尚未完成 AI 分析，无可查看报告')
    return
  }
  previewTask.value = t
  previewVisible.value = true
  previewLoading.value = true
  reportDetail.value = null
  try {
    reportDetail.value = await ScreeningApi.getScreeningReport(t.id)
  } catch {
    /* 静默 */
  } finally {
    previewLoading.value = false
  }
}

/* ===== 导出 PDF ===== */
const exportingMap = ref<Record<string, boolean>>({})
const exportPdf = async (t: Task) => {
  exportingMap.value[t.id] = true
  try {
    await ScreeningApi.exportReportPdf(
      t.id,
      `${t.patientId || t.id}_${t.patientName || ''}_DR筛查报告.pdf`
    )
    ElMessage.success('报告 PDF 导出完成')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    exportingMap.value[t.id] = false
  }
}

/* ===== 列表 Excel 导出 ===== */
const summaryExporting = ref(false)
const exportListExcel = async () => {
  summaryExporting.value = true
  try {
    await ScreeningApi.exportScreeningExcel(
      buildQuery(),
      `screening_cases_${Date.now()}.xlsx`
    )
    ElMessage.success('当前列表已导出 Excel')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    summaryExporting.value = false
  }
}

/* ===== 绑定手机号 ===== */
const bindVisible = ref(false)
const bindTask = ref<Task | null>(null)
const bindPhoneInput = ref('')
const bindSaving = ref(false)
const phoneReg = /^1[3-9]\d{9}$/

const openBind = (t: Task) => {
  if (!canManage.value) {
    ElMessage.warning('当前角色无权绑定病例手机号')
    return
  }
  bindTask.value = t
  bindPhoneInput.value = t.patientPhone || ''
  bindVisible.value = true
}

const submitBind = async () => {
  if (!bindTask.value) return
  const phone = bindPhoneInput.value.trim()
  if (phone && !phoneReg.test(phone)) {
    ElMessage.warning('请输入 11 位有效手机号（或留空清除绑定）')
    return
  }
  try {
    await ElMessageBox.confirm(
      phone
        ? `确认将病例 ${bindTask.value.id} 绑定到手机号 ${phone}？`
        : `确认清除病例 ${bindTask.value.id} 的手机号绑定？`,
      '操作确认',
      { type: 'warning', confirmButtonText: '确认绑定', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  bindSaving.value = true
  try {
    if (!bindTask.value.caseId) {
      ElMessage.warning('无法获取病例数据库 ID，无法绑定')
      return
    }
    await PatientApi.bindCasePhone(bindTask.value.caseId, phone)
    // 写入共享 overlay：分析任务队列页立即可见
    if (phone) {
      bindingStore.setBinding(
        { caseId: bindTask.value.caseId, patientId: bindTask.value.patientId },
        phone,
        true,
      )
    } else {
      bindingStore.clearBinding({
        caseId: bindTask.value.caseId,
        patientId: bindTask.value.patientId,
      })
    }
    bindVisible.value = false
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '绑定失败')
  } finally {
    bindSaving.value = false
  }
}

/* ===== 确认报告（同步至病患账号） ===== */
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
  // 强校验：未绑定手机号无法确认报告（确认后病患账号侧拿不到）
  if (!t.patientPhone) {
    try {
      await ElMessageBox.confirm(
        '该病例尚未绑定病患手机号，确认报告后无法推送至病患账号。\n是否立即绑定手机号？',
        '需要先绑定手机号',
        {
          type: 'warning',
          confirmButtonText: '去绑定',
          cancelButtonText: '取消',
        },
      )
      openBind(t)
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
        cancelButtonText: '取消',
        dangerouslyUseHTMLString: false
      }
    )
  } catch {
    return
  }
  confirmingMap.value[t.id] = true
  try {
    const res = await ScreeningApi.confirmReport({ taskId: t.id })
    ElMessageBox.alert(
      res.patientBound
        ? `已确认并同步至病患账号（${res.patientPhone}）。`
        : '已确认。该病例尚未绑定病患账号，病患账号侧暂不可见。',
      '操作完成',
      {
        confirmButtonText: '查看报告',
        callback: () => showReport({ ...t, confirmed: true })
      }
    )
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '确认失败')
  } finally {
    confirmingMap.value[t.id] = false
  }
}

/* ===== 编辑 / 补充病例（仅医生 / 管理员） ===== */
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
}

/* ===== 移除 ===== */
const removeTask = async (t: Task) => {
  if (!canManage.value) {
    ElMessage.warning('当前角色无权移除病例')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要移除病例 ${t.id}（${t.patientName}）吗？此操作不可恢复。`,
      '操作确认',
      { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await ScreeningApi.deleteScreeningTask(t.id)
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '移除失败')
  }
}

/* ===== 批量勾选 / 批量删除 ===== */
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
    ElMessage.warning('当前角色无权批量删除病例')
    return
  }
  if (selectedTasks.value.length === 0) {
    ElMessage.info('请先勾选要删除的病例')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定批量删除已勾选的 ${selectedTasks.value.length} 条病例？此操作不可恢复。`,
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
    selectedTasks.value = []
    fetchList()
    if (res.failedCount > 0) {
      ElMessage.warning(
        `批量删除完成：成功 ${res.successCount} 条，失败 ${res.failedCount} 条`
      )
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '批量删除失败')
  } finally {
    batchLoading.value = false
  }
}

/* ===== 生命周期 ===== */
onMounted(fetchList)
// keep-alive 下重新进入也刷一次
onActivated(fetchList)

/* ===== 工具 ===== */
const phoneMask = (p: string) => {
  if (!p || p.length < 7) return p || '—'
  return `${p.slice(0, 3)}****${p.slice(-4)}`
}
</script>

<template>
  <div class="case-search">
    <!-- 顶部标题 -->
    <header class="page-head">
      <div class="title-block">
        <div class="dot blue"></div>
        <div>
          <div class="title">病例检索</div>
          <div class="subtitle">已完成 AI 分析的病例 · 支持多条件筛选 / 报告确认 / 病患账号同步</div>
        </div>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" @click="onRefresh">刷新</el-button>
        <el-button
          type="primary"
          :icon="Download"
          :loading="summaryExporting"
          @click="exportListExcel"
        >
          导出当前列表
        </el-button>
      </div>
    </header>

    <!-- 检索条件 -->
    <section class="filter-card">
      <DynamicFilter
        v-model="filter"
        :schema="SCREENING_ARCHIVE_FILTER"
        :loading="listLoading"
        @submit="onSearch"
        @reset="onReset"
        @refresh="onRefresh"
      />
    </section>

    <!-- 列表 -->
    <section class="list-card">
      <!-- 批量操作条（仅医生 / 管理员；不破坏现有布局） -->
      <div
        v-if="canManage && selectedTasks.length > 0"
        class="batch-bar"
      >
        <span class="batch-info">已勾选 {{ selectedTasks.length }} 条</span>
        <el-button
          type="danger"
          size="small"
          :icon="Delete"
          :loading="batchLoading"
          @click="batchDeleteTasks"
        >
          批量删除
        </el-button>
        <el-button size="small" text @click="clearSelection">取消选择</el-button>
      </div>

      <el-table
        v-loading="listLoading"
        element-loading-text="正在加载病例…"
        :data="tasks"
        stripe
        size="default"
        height="100%"
        style="width: 100%"
        @selection-change="onSelectionChange"
      >
        <el-table-column
          v-if="canManage"
          type="selection"
          width="48"
          :selectable="() => true"
        />
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="病例编号" prop="id" min-width="160" show-overflow-tooltip />
        <el-table-column label="患者ID" prop="patientId" width="120" show-overflow-tooltip />
        <el-table-column label="姓名" prop="patientName" width="100" />
        <el-table-column label="性别 / 年龄" width="110">
          <template #default="{ row }">{{ row.gender }} / {{ row.age }}</template>
        </el-table-column>
        <el-table-column label="眼别" width="100">
          <template #default="{ row }">{{ eyeMap[row.eye as Eye] }}</template>
        </el-table-column>
        <el-table-column label="手机号" width="180">
          <template #default="{ row }">
            <template v-if="row.patientPhone">
              <span class="phone-num">{{ phoneMask(row.patientPhone) }}</span>
              <el-tag
                v-if="row.patientBound"
                type="success"
                size="small"
                effect="plain"
                style="margin-left: 4px"
              >
                已关联
              </el-tag>
              <el-tag
                v-else
                type="info"
                size="small"
                effect="plain"
                style="margin-left: 4px"
              >
                未关联
              </el-tag>
            </template>
            <span v-else class="muted">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="120">
          <template #default="{ row }">
            <span v-if="!row.risk" class="muted">—</span>
            <span v-else :class="['hy-risk-tag', 'hy-risk-' + row.risk]">
              {{ riskTextMap[row.risk as RiskLevel] }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag
              :type="(statusMap[row.status as Status]?.type as any)"
              size="small"
              effect="dark"
            >
              {{ statusMap[row.status as Status]?.text }}
            </el-tag>
            <el-tag
              v-if="row.confirmed"
              type="success"
              size="small"
              effect="plain"
              style="margin-left: 4px"
            >
              已确认
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" prop="createdAt" min-width="170" />
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
            <span v-else class="muted-tag">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="380" fixed="right">
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
              v-if="canManage && !row.patientPhone"
              text
              type="primary"
              :icon="Iphone"
              @click="openBind(row)"
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
              type="warning"
              :icon="CircleCheck"
              :disabled="row.status !== 'done' || row.confirmed"
              :loading="!!confirmingMap[row.id]"
              @click="confirmReport(row)"
            >
              {{ row.confirmed ? '已确认' : '确认报告' }}
            </el-button>
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
              :icon="Delete"
              @click="removeTask(row)"
            >
              移除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">
            {{ listLoading ? '加载中…' : '没有匹配的病例，可调整筛选条件后重试' }}
          </div>
        </template>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[20, 50, 100, 200]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </section>

    <!-- 报告预览 -->
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
            <el-descriptions-item label="病例编号">{{ previewTask.id }}</el-descriptions-item>
            <el-descriptions-item label="患者ID">{{ previewTask.patientId }}</el-descriptions-item>
            <el-descriptions-item label="姓名">{{ previewTask.patientName }}</el-descriptions-item>
            <el-descriptions-item label="性别 / 年龄">
              {{ previewTask.gender }} / {{ previewTask.age }} 岁
            </el-descriptions-item>
            <el-descriptions-item label="眼别">{{ eyeMap[previewTask.eye] }}</el-descriptions-item>
            <el-descriptions-item label="手机号">
              {{ phoneMask(previewTask.patientPhone) }}
            </el-descriptions-item>
            <el-descriptions-item label="DR 分级">{{ previewTask.dr || '—' }}</el-descriptions-item>
            <el-descriptions-item label="AI 置信度">
              {{ (previewTask.confidence * 100).toFixed(1) }}%
            </el-descriptions-item>
            <el-descriptions-item label="提交时间" :span="2">
              {{ previewTask.createdAt }}
            </el-descriptions-item>
          </el-descriptions>
          <div class="report-conclusion">
            <div class="ck-title">AI 辅助诊断意见</div>
            <p v-if="reportDetail?.conclusion">{{ reportDetail.conclusion }}</p>
            <p v-else>{{ previewTask.remark || '暂无 AI 结论' }}</p>
            <p v-if="reportDetail?.suggestion" class="suggestion">
              <b>建议处置：</b>{{ reportDetail.suggestion }}
            </p>
          </div>

          <!-- CSU-EYES 智能诊断结果（如有） -->
          <div v-if="previewTask.diagnosisType" class="report-diagnosis">
            <div class="ck-title">
              CSU-EYES 智能诊断
              <el-tag
                size="small"
                :type="previewTask.diagnosisType === 'MA' ? '' : previewTask.diagnosisType === 'DR' ? 'warning' : 'success'"
                effect="dark"
                style="margin-left: 6px"
              >
                {{ previewTask.diagnosisType === 'MA' ? '微动脉瘤检测' : previewTask.diagnosisType === 'DR' ? 'DR 分级' : '综合诊断' }}
              </el-tag>
            </div>
            <p class="diag-summary-text">{{ previewTask.diagnosisSummary || '—' }}</p>
            <div v-if="previewTask.heatmapUrl" class="diag-heatmap">
              <img :src="previewTask.heatmapUrl" alt="diagnosis heatmap" />
              <div class="cap">病灶标注 / 热力图</div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
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

    <!-- 绑定手机号弹窗 -->
    <el-dialog
      v-model="bindVisible"
      title="绑定病患手机号"
      width="440"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="bind-tip" v-if="bindTask">
        将病例 <strong>{{ bindTask.id }}</strong>（{{ bindTask.patientName }}）
        与病患账号手机号建立绑定，绑定后病患登录可在【我的报告】查看本人报告。
      </div>
      <el-input
        v-model="bindPhoneInput"
        placeholder="11 位手机号（留空可清除绑定）"
        maxlength="11"
        :prefix-icon="Iphone"
        clearable
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="bindVisible = false">取消</el-button>
        <el-button type="primary" :loading="bindSaving" @click="submitBind">
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
.case-search {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px 24px;
  min-height: 100%;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  background: #ffffff;
  border: 1px solid #e6effe;
  border-radius: 12px;
  padding: 18px 22px;
}
.title-block {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title {
  font-size: 18px;
  font-weight: 700;
  color: #1d2129;
}
.subtitle {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.dot.blue {
  background: #1677ff;
  box-shadow: 0 0 0 4px rgba(22, 119, 255, 0.18);
}
.head-actions {
  display: flex;
  gap: 10px;
}

.filter-card {
  background: #ffffff;
  border: 1px solid #e6effe;
  border-radius: 12px;
  padding: 16px 20px 4px;
}
.filter-form :deep(.el-form-item) {
  margin-right: 16px;
  margin-bottom: 12px;
}

.list-card {
  background: #ffffff;
  border: 1px solid #e6effe;
  border-radius: 12px;
  padding: 14px 16px 16px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 480px;
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
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

.phone-num {
  font-family: ui-monospace, SFMono-Regular, monospace;
  color: #1d2129;
}
.muted { color: #c9cdd4; }
.muted-tag { color: #c9cdd4; }
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
.report-diagnosis {
  margin-top: 12px;
  padding: 12px 14px;
  background: #fafbfc;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
}
.diag-summary-text {
  margin: 4px 0 8px;
  color: #1d2129;
  font-weight: 500;
}
.diag-heatmap {
  margin-top: 8px;
  text-align: center;
}
.diag-heatmap img {
  max-width: 100%;
  max-height: 320px;
  border-radius: 6px;
  border: 1px solid #e5e6eb;
}
.diag-heatmap .cap {
  color: #86909c;
  font-size: 12px;
  margin-top: 4px;
}

.bound-tag {
  margin: 0 6px;
  vertical-align: middle;
}

.empty {
  padding: 40px 0;
  color: #c9cdd4;
  font-size: 14px;
}

.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.bind-tip {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.7;
  background: #f7faff;
  border: 1px dashed #d0e0fb;
  border-radius: 8px;
  padding: 10px 12px;
}

/* 报告预览样式 */
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

/* 风险标签（与全局变量保持一致） */
.hy-risk-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 11px;
  font-size: 12px;
  font-weight: 600;
}
.hy-risk-red {
  background: rgba(245, 63, 63, 0.12);
  color: #f53f3f;
}
.hy-risk-yellow {
  background: rgba(255, 125, 0, 0.14);
  color: #ff7d00;
}
.hy-risk-green {
  background: rgba(0, 180, 42, 0.14);
  color: #00b42a;
}
</style>
