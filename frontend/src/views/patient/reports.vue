<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Document,
  Download,
  Refresh,
  View
} from '@element-plus/icons-vue'

import { PatientApi } from '@/api'
import { useUserStore } from '@/stores/user'
import RiskTag from '@/components/tags/RiskTag.vue'
import DRGradeTag from '@/components/tags/DRGradeTag.vue'

const userStore = useUserStore()

/* ========== 用户 ========== */
const userInfo = computed(() => userStore.userInfo)
const displayName = computed(() => userStore.displayName)
const phone = computed(() => userInfo.value.phone || userInfo.value.username || '')

/* ========== 列表 ========== */
const loading = ref(false)
const reports = ref<PatientApi.PatientReport[]>([])
const total = ref(0)
const query = ref<PatientApi.PatientReportListQuery>({ page: 1, pageSize: 10 })

const fetchList = async () => {
  loading.value = true
  try {
    const res = await PatientApi.getMyReports(query.value)
    reports.value = res.list || []
    total.value = res.total || 0
  } catch {
    reports.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const onPage = (p: number) => {
  query.value.page = p
  fetchList()
}

/* ========== 详情 ========== */
const detailVisible = ref(false)
const detail = ref<PatientApi.PatientReport | null>(null)
const detailLoading = ref(false)

const openDetail = async (item: PatientApi.PatientReport) => {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await PatientApi.getMyReportDetail(item.caseId)
  } catch {
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

/* ========== 影像预览 ========== */
const imagePreviewVisible = ref(false)
const previewIndex = ref(0)
const openImagePreview = (i: number) => {
  previewIndex.value = i
  imagePreviewVisible.value = true
}

/* ========== DR 分级 / 风险标签（共享 utils） ========== */
/* ========== DR 分级 / 风险标签 已迁移至公共组件 + v-dr-color directive ========== */

/* ========== 报告 PDF 预览 / 下载 ========== */
const pdfBusy = ref<Record<number, 'preview' | 'download' | ''>>({})
const previewBlobUrls: string[] = []

const isPdfBusy = (caseId: number, kind: 'preview' | 'download') =>
  pdfBusy.value[caseId] === kind

const previewPdf = async (item: PatientApi.PatientReport) => {
  if (!item.pdfAvailable) {
    ElMessage.warning('该报告尚未确认或暂无 PDF，请联系医生确认后再试')
    return
  }
  if (pdfBusy.value[item.caseId]) return
  pdfBusy.value[item.caseId] = 'preview'
  try {
    const url = await PatientApi.previewReportPdf(item.caseId)
    previewBlobUrls.push(url)
    const win = window.open(url, '_blank', 'noopener,noreferrer')
    if (!win) {
      ElMessage.warning('浏览器拦截了新标签页，请允许弹出后重试')
    }
  } catch {
    ElMessage.error('PDF 预览失败，请稍后重试')
  } finally {
    pdfBusy.value[item.caseId] = ''
  }
}

const downloadPdf = async (item: PatientApi.PatientReport) => {
  if (!item.pdfAvailable) {
    ElMessage.warning('该报告尚未确认或暂无 PDF，请联系医生确认后再试')
    return
  }
  if (pdfBusy.value[item.caseId]) return
  pdfBusy.value[item.caseId] = 'download'
  try {
    const filename = `${item.patientName || '体检'}_${item.caseNo || item.caseId}.pdf`
    await PatientApi.downloadReportPdf(item.caseId, filename)
    ElMessage.success('已开始下载')
  } catch {
    ElMessage.error('PDF 下载失败，请稍后重试')
  } finally {
    pdfBusy.value[item.caseId] = ''
  }
}

onBeforeUnmount(() => {
  previewBlobUrls.forEach((u) => URL.revokeObjectURL(u))
  previewBlobUrls.length = 0
})

onMounted(fetchList)
</script>

<template>
  <div class="patient-page">
    <main class="page-body">
      <header class="page-head">
        <div class="head-left">
          <h2>我的病例</h2>
          <div class="muted">查看与您手机号关联的体检记录与诊断结论</div>
        </div>
        <div class="head-right">
          <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
        </div>
      </header>

      <!-- 摘要 -->
      <div class="summary-card">
        <div class="hello">
          您好，<strong>{{ displayName }}</strong>
        </div>
        <div class="hint">
          以下是与您手机号 <strong>{{ phone || '—' }}</strong> 关联的体检记录
          （共 {{ total }} 份），点击可查看诊断结论与影像资料。
        </div>
      </div>

      <!-- 报告列表 -->
      <div v-loading="loading" class="report-list">
        <el-empty v-if="!loading && reports.length === 0" description="暂无您的体检报告">
          <template #description>
            <p>未查询到与您手机号关联的体检记录。</p>
            <p class="muted">请联系前台体检中心确认报告是否已绑定手机号。</p>
          </template>
        </el-empty>

        <div v-for="r in reports" :key="r.caseId" class="report-item">
          <div class="head">
            <div class="title-line">
              <el-icon><document /></el-icon>
              <span class="case-no">{{ r.caseNo }}</span>
              <el-tag size="small" type="info">{{ r.statusText }}</el-tag>
              <RiskTag
                v-if="r.riskLevelText"
                :level="r.riskLevel"
                :text="r.riskLevelText"
                effect="dark"
              />
              <el-tag
                v-if="r.referralRequired"
                size="small"
                type="danger"
              >
                建议转诊
              </el-tag>
            </div>
            <div class="time">
              {{ r.submitAt || r.createdAt }}
            </div>
          </div>

          <div class="body">
            <div class="left-col">
              <div class="patient-line">
                <span>{{ r.patientName || '—' }}</span>
                <span>·</span>
                <span>{{ r.gender || '—' }}</span>
                <span v-if="r.age">·</span>
                <span v-if="r.age">{{ r.age }} 岁</span>
              </div>
              <div v-if="r.chiefComplaint" class="meta-line">
                <strong>主诉：</strong>{{ r.chiefComplaint }}
              </div>
              <div v-if="r.medicalHistory" class="meta-line">
                <strong>病史：</strong>{{ r.medicalHistory }}
              </div>
              <div v-if="r.drGradeText" class="grade-line">
                <span class="label">DR 分级：</span>
                <DRGradeTag :grade="r.drGrade" :text="r.drGradeText" />
              </div>
              <div v-if="r.doctorDiagnosis" class="diag-line">
                <strong>诊断结论：</strong>{{ r.doctorDiagnosis }}
                <span v-if="r.doctorName" class="muted">— {{ r.doctorName }} 医生</span>
              </div>
            </div>
            <div class="right-col">
              <div class="thumbs">
                <el-image
                  v-for="(img, i) in r.images.slice(0, 3)"
                  :key="i"
                  :src="img"
                  fit="cover"
                  class="thumb"
                >
                  <template #error>
                    <div class="thumb-error">影像加载失败</div>
                  </template>
                </el-image>
              </div>
              <el-button
                type="primary"
                :icon="View"
                size="default"
                style="margin-top: 8px; width: 100%"
                @click="openDetail(r)"
              >
                查看完整报告
              </el-button>
              <el-button
                type="success"
                :icon="Document"
                size="default"
                style="margin-top: 6px; width: 100%; margin-left: 0"
                :loading="isPdfBusy(r.caseId, 'preview')"
                :disabled="!r.pdfAvailable"
                @click="previewPdf(r)"
              >
                {{ r.pdfAvailable ? '在线预览 PDF' : '报告未确认' }}
              </el-button>
              <el-button
                type="warning"
                :icon="Download"
                size="default"
                style="margin-top: 6px; width: 100%; margin-left: 0"
                :loading="isPdfBusy(r.caseId, 'download')"
                :disabled="!r.pdfAvailable"
                @click="downloadPdf(r)"
              >
                下载 PDF
              </el-button>
              <div v-if="!r.pdfAvailable" class="pdf-hint">
                医生确认后即可下载
              </div>
            </div>
          </div>
        </div>
      </div>

      <el-pagination
        v-if="total > 0"
        :current-page="query.page"
        :page-size="query.pageSize"
        :total="total"
        layout="total, prev, pager, next, jumper"
        class="pager"
        @current-change="onPage"
      />
    </main>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      width="820px"
      destroy-on-close
      :title="detail ? `体检报告 ${detail.caseNo}` : '体检报告'"
    >
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="detail-meta">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="病例编号">{{ detail.caseNo }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag size="small">{{ detail.statusText }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="姓名">{{ detail.patientName || '—' }}</el-descriptions-item>
              <el-descriptions-item label="性别 / 年龄">
                {{ detail.gender || '—' }} · {{ detail.age || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="主诉" :span="2">
                {{ detail.chiefComplaint || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="病史" :span="2">
                {{ detail.medicalHistory || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="送检时间">
                {{ detail.submitAt || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="复核时间">
                {{ detail.reviewAt || '—' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- 诊断结论 -->
          <div class="conclusion">
            <h4>诊断结论</h4>
            <div v-if="detail.drGradeText" class="grade-card">
              <div class="grade-label">DR 分级</div>
              <div v-dr-color="detail.drGrade" class="grade-val">
                {{ detail.drGradeText }}
              </div>
            </div>
            <div class="risk-row">
              <RiskTag
                v-if="detail.riskLevelText"
                :level="detail.riskLevel"
                :text="`风险等级：${detail.riskLevelText}`"
                effect="dark"
                size="default"
              />
              <el-tag v-if="detail.referralRequired" type="danger" size="default">
                建议尽快转诊
              </el-tag>
              <span v-if="detail.riskScore" class="score">
                AI 风险评分：{{ (detail.riskScore * 100).toFixed(1) }}
              </span>
            </div>
            <div v-if="detail.lesions && detail.lesions.length" class="lesion-list">
              <div class="sub-title">检出病灶</div>
              <el-table :data="detail.lesions" border size="small">
                <el-table-column prop="type" label="类型" />
                <el-table-column prop="count" label="数量" width="100" />
                <el-table-column prop="score" label="置信度" width="120">
                  <template #default="{ row }">
                    <span v-if="row.score">{{ (row.score * 100).toFixed(1) }}%</span>
                    <span v-else>—</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <div v-if="detail.doctorDiagnosis" class="doctor-text">
              <div class="sub-title">医生最终诊断</div>
              <p>{{ detail.doctorDiagnosis }}</p>
              <div class="doctor-sign">
                — {{ detail.doctorName || '复核医师' }} 医生
              </div>
            </div>
          </div>

          <!-- 影像预览 -->
          <div v-if="detail.images && detail.images.length" class="images">
            <h4>影像资料 ({{ detail.images.length }})</h4>
            <div class="image-grid">
              <el-image
                v-for="(img, i) in detail.images"
                :key="i"
                :src="img"
                fit="cover"
                class="grid-thumb"
                @click="openImagePreview(i)"
              >
                <template #error>
                  <div class="thumb-error">影像加载失败</div>
                </template>
              </el-image>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <div v-if="detail" class="dialog-footer">
          <el-button
            type="success"
            :icon="Document"
            :loading="isPdfBusy(detail.caseId, 'preview')"
            :disabled="!detail.pdfAvailable"
            @click="previewPdf(detail)"
          >
            在线预览 PDF
          </el-button>
          <el-button
            type="warning"
            :icon="Download"
            :loading="isPdfBusy(detail.caseId, 'download')"
            :disabled="!detail.pdfAvailable"
            @click="downloadPdf(detail)"
          >
            下载 PDF
          </el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 全屏影像预览 -->
    <el-image-viewer
      v-if="imagePreviewVisible && detail?.images?.length"
      :url-list="detail.images"
      :initial-index="previewIndex"
      hide-on-click-modal
      @close="imagePreviewVisible = false"
    />
  </div>
</template>

<style scoped>
.patient-page {
  min-height: 100%;
}
.page-body {
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 32px 40px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 12px;
  flex-wrap: wrap;
}
.head-left h2 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
}
.head-left .muted {
  color: #86909c;
  font-size: 13px;
}
.head-right {
  display: flex;
  gap: 8px;
}

.summary-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  border: 1px solid #e6effe;
  margin-bottom: 16px;
}
.hello {
  font-size: 16px;
  color: #1d2129;
  margin-bottom: 6px;
}
.hint {
  font-size: 13px;
  color: #86909c;
  line-height: 1.7;
}
.muted {
  color: #c9cdd4;
}

.report-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 200px;
}
.report-item {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 16px 20px;
  transition: box-shadow 0.2s;
}
.report-item:hover {
  box-shadow: 0 4px 18px rgba(22, 119, 255, 0.08);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  flex-wrap: wrap;
  gap: 8px;
}
.title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.case-no {
  font-family: 'Consolas', monospace;
  font-weight: 600;
  color: #1677ff;
}
.time {
  color: #86909c;
  font-size: 12px;
}
.body {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 18px;
}
.patient-line {
  display: flex;
  gap: 6px;
  font-size: 13px;
  color: #4e5969;
  margin-bottom: 6px;
}
.meta-line {
  font-size: 13px;
  color: #4e5969;
  margin-bottom: 4px;
}
.grade-line {
  margin-top: 8px;
  font-size: 14px;
}
.grade-line .label {
  color: #86909c;
}
.diag-line {
  margin-top: 6px;
  font-size: 13px;
  color: #1d2129;
  background: #f5f7fa;
  padding: 8px 10px;
  border-radius: 6px;
  border-left: 3px solid #1677ff;
}
.right-col {
  display: flex;
  flex-direction: column;
}
.thumbs {
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px;
}
.thumb {
  width: 100%;
  height: 96px;
  border-radius: 6px;
  background: #000;
}
.thumb-error {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c9cdd4;
  font-size: 11px;
  background: #1d2129;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

/* 详情弹窗 */
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-body h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}
.grade-card {
  background: #fafbfc;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.grade-label {
  color: #86909c;
  font-size: 13px;
}
.grade-val {
  font-size: 18px;
  font-weight: 700;
}
.risk-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
  flex-wrap: wrap;
}
.score {
  font-size: 13px;
  color: #4e5969;
}
.lesion-list {
  margin-top: 12px;
}
.sub-title {
  font-size: 13px;
  color: #4e5969;
  margin-bottom: 6px;
}
.doctor-text {
  margin-top: 12px;
  background: #eef4ff;
  border-radius: 6px;
  padding: 12px 14px;
}
.doctor-text p {
  margin: 0;
  color: #1d2129;
  line-height: 1.7;
}
.doctor-sign {
  margin-top: 8px;
  text-align: right;
  font-size: 12px;
  color: #86909c;
}
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}
.grid-thumb {
  width: 100%;
  height: 110px;
  border-radius: 6px;
  background: #000;
  cursor: zoom-in;
}
.pdf-hint {
  margin-top: 6px;
  font-size: 11px;
  color: #c9cdd4;
  text-align: center;
  line-height: 1.5;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
