<script setup lang="ts">
/**
 * 管理员 · IDRiD 多病灶数据集批量导入
 * 调后端 POST /admin/import/idrid（同步执行）
 *
 * 流程：
 *  1. 配置源目录 / limit / dry-run
 *  2. 执行导入 → 后端把 9 类影像（原图 + 5 病灶 mask + 3 mask 产物）登记到 biz_case_image
 *  3. 完成后展示统计：成功 / 跳过 / 影像不完整 / DR 分级分布 / 案例样本
 *  4. 一键跳「病例库」筛选「仅看影像不完整」
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload,
  Refresh,
  WarningFilled,
  Files,
  Picture,
  CircleCheck,
  CircleClose,
  User,
  UserFilled
} from '@element-plus/icons-vue'

import { CaseImageApi } from '@/api'

type IdridResult = CaseImageApi.IdridImportResult
type IdridProbe = CaseImageApi.IdridProbeResult
type BackfillResult = CaseImageApi.BackfillPatientResult

const props = defineProps<{
  canManage: boolean
}>()

const router = useRouter()

const form = reactive<{
  sourcePath: string
  limit: number | null
  dryRun: boolean
  skipExisting: boolean
}>({
  sourcePath: '',
  limit: 5,
  dryRun: true,
  skipExisting: true
})

const running = ref(false)
const probing = ref(false)
const probe = ref<IdridProbe | null>(null)
const lastResult = ref<IdridResult | null>(null)
const lastRunAt = ref<string>('')

const runProbe = async (path?: string) => {
  probing.value = true
  try {
    const res = await CaseImageApi.probeIdrid(path)
    probe.value = res
    if (!form.sourcePath && res.sourcePath) {
      form.sourcePath = res.sourcePath
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '探测约定目录失败')
  } finally {
    probing.value = false
  }
}

onMounted(() => {
  runProbe()
})

const elapsedText = computed(() => {
  const sec = lastResult.value?.elapsedSec || 0
  if (sec < 60) return `${sec.toFixed(1)} 秒`
  const m = Math.floor(sec / 60)
  const s = (sec % 60).toFixed(0)
  return `${m} 分 ${s} 秒`
})

const gradeRows = computed(() => {
  const map = lastResult.value?.gradeDistribution || {}
  const rows = Object.entries(map).map(([k, v]) => ({ grade: k, count: Number(v) }))
  rows.sort((a, b) => a.grade.localeCompare(b.grade))
  return rows
})

const sampleCaseSns = computed(() => lastResult.value?.sampleCaseSns || [])

const onRun = async () => {
  if (!form.dryRun) {
    try {
      await ElMessageBox.confirm(
        `确认正式入库？导入后默认未发布，学员不可见。\n\n源目录：${
          form.sourcePath.trim() || '服务器约定目录'
        }\n${form.limit ? `限制：${form.limit} 例\n` : ''}${
          form.skipExisting ? '已存在病例将跳过\n' : '已存在病例将覆盖（重新登记影像）\n'
        }\n该操作会复制文件并写入数据库，可能耗时数十秒。`,
        '正式入库',
        { type: 'warning', confirmButtonText: '开始入库', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }
  running.value = true
  try {
    const res = await CaseImageApi.importIdrid({
      sourcePath: form.sourcePath.trim() || undefined,
      limit: form.limit && form.limit > 0 ? form.limit : undefined,
      dryRun: form.dryRun,
      skipExisting: form.skipExisting
    })
    lastResult.value = res
    lastRunAt.value = new Date().toLocaleString()
    ElMessage.success(
      form.dryRun
        ? `Dry-run 完成，预计可导入 ${res.importedCases} 例，未写库`
        : `已入库 ${res.importedCases} 例（默认未发布），请回病例库完善金标准 / 加入实训`
    )
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败，请检查服务器约定目录')
  } finally {
    running.value = false
  }
}

const goCaseLibrary = () => {
  router.push({ path: '/training/cases', query: { keyword: 'IDRiD' } })
}

const goIncomplete = () => {
  router.push({ path: '/training/cases', query: { onlyIncomplete: '1' } })
}

const reset = () => {
  lastResult.value = null
  lastRunAt.value = ''
}

/* ========== 旧病例补齐模拟患者信息 ========== */
const backfilling = ref(false)
const backfillResult = ref<BackfillResult | null>(null)

const runBackfill = async (overwrite = false) => {
  try {
    await ElMessageBox.confirm(
      overwrite
        ? '【危险】将覆盖所有病例的姓名/手机号/年龄，已有数据会被替换。确定继续？'
        : '将给缺失模拟患者信息（姓名/性别/年龄/手机号/case_sn）的旧病例自动生成。已有数据保留不变。',
      '一键补齐患者信息',
      {
        type: overwrite ? 'error' : 'warning',
        confirmButtonText: overwrite ? '强制覆盖' : '开始补齐',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }
  backfilling.value = true
  try {
    backfillResult.value = await CaseImageApi.backfillPatientInfo({
      onlyEmpty: !overwrite,
      overwrite
    })
  } catch (e: any) {
    ElMessage.error(e?.message || '补齐失败')
  } finally {
    backfilling.value = false
  }
}
</script>

<template>
  <div class="idrid-section">
    <div v-if="!canManage" class="card">
      <el-alert
        title="当前账号无 IDRiD 批量导入权限"
        type="warning"
        description="仅平台管理员（ADMIN）可执行 IDRiD 批量导入。"
        :closable="false"
        show-icon
      />
    </div>

    <template v-else>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="flow-alert"
        title="导入后默认未发布，学员不可见"
      >
        运维把数据集放到服务器约定目录 → 先勾 Dry-run、限制 5 条只扫描 →
        取消 Dry-run 正式入库 → 回病例库走「完善金标准 / 加入实训」再给学生。
      </el-alert>

      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <el-icon class="title-icon"><Files /></el-icon>
            服务器约定目录
          </div>
          <el-button
            size="small"
            :icon="Refresh"
            :loading="probing"
            @click="runProbe(form.sourcePath.trim() || undefined)"
          >
            重新探测
          </el-button>
        </div>
        <el-alert
          v-if="probe"
          :type="probe.ready ? 'success' : 'warning'"
          :closable="false"
          show-icon
          :title="probe.ready ? '约定目录就绪' : '约定目录未就绪'"
        >
          {{ probe.hint }}
          <div v-if="probe.ready" class="probe-meta">
            训练 {{ probe.trainCount }} 张 · 测试 {{ probe.testCount }} 张 · 路径
            <code>{{ probe.sourcePath }}</code>
          </div>
        </el-alert>
        <div v-else class="muted">正在探测服务器约定目录…</div>
      </div>

      <!-- 旧病例补齐卡片 -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <el-icon class="title-icon"><User /></el-icon>
            旧病例 · 一键补齐模拟患者信息
          </div>
          <span class="muted">
            为缺失「姓名 / 性别 / 年龄 / 手机号 / case_sn」的旧病例自动生成虚拟但合规的患者信息
          </span>
        </div>

        <div class="backfill-actions">
          <el-button
            type="primary"
            :icon="UserFilled"
            :loading="backfilling"
            @click="runBackfill(false)"
          >
            仅补缺失字段（推荐）
          </el-button>
          <el-button
            type="danger"
            plain
            :loading="backfilling"
            :disabled="backfilling"
            @click="runBackfill(true)"
          >
            强制覆盖全部
          </el-button>
        </div>

        <div v-if="backfillResult" class="backfill-result">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="筛查病例">
              已扫描 {{ backfillResult.screeningTotal }} 条
            </el-descriptions-item>
            <el-descriptions-item label="筛查 · 已补齐">
              <b style="color:#1677ff">{{ backfillResult.screeningFilled }}</b>
            </el-descriptions-item>
            <el-descriptions-item label="case_sn 补齐">
              <b style="color:#00b42a">{{ backfillResult.caseSnFilled }}</b>
            </el-descriptions-item>
            <el-descriptions-item label="实训病例">
              已扫描 {{ backfillResult.trainingTotal }} 条
            </el-descriptions-item>
            <el-descriptions-item label="实训 · 已补齐" :span="2">
              <b style="color:#1677ff">{{ backfillResult.trainingFilled }}</b>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 配置卡片 -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <el-icon class="title-icon"><Upload /></el-icon>
            IDRiD 多病灶数据集 · 批量导入
          </div>
          <span class="muted">
            将原图 + 5 病灶 mask（MA / HE / EX / SE / OD）+ 彩色 mask 一键登记为「实训病例 + 体检病例」
          </span>
        </div>

        <el-form :model="form" label-width="120px" class="form" :disabled="running">
          <el-form-item label="源目录路径">
            <el-input
              v-model="form.sourcePath"
              placeholder="留空 = 使用服务器约定目录"
              clearable
            >
              <template #prepend>服务器路径</template>
            </el-input>
            <div class="hint">
              <strong>这是后端服务器上的路径，不是你这台电脑上的路径。</strong>
              运维先把数据集放到约定目录（容器部署时还需挂载进容器）。
              目录下应包含「1. Original Images」「2. All Segmentation Groundtruths」
              「3. IDRID_4_lesion_processed」三个子目录。正式入库会把文件复制到
              <code>backend/app/static/training/idrid/</code> 下并按 role 分目录。
            </div>
          </el-form-item>

          <el-form-item label="限制数量">
            <el-input-number
              v-model="form.limit"
              :min="0"
              :max="500"
              :step="5"
              placeholder="0 = 全部"
              style="width: 220px"
            />
            <span class="hint" style="margin-left: 12px">
              试跑填 5；0 表示扫描/导入全部
            </span>
          </el-form-item>

          <el-form-item label="选项">
            <el-checkbox v-model="form.skipExisting">
              已存在 case_no 则跳过（推荐）
            </el-checkbox>
            <el-checkbox v-model="form.dryRun" style="margin-left: 18px">
              Dry-run（仅扫描，不落盘、不写库）
            </el-checkbox>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :icon="Upload"
              :loading="running"
              @click="onRun"
            >
              {{ form.dryRun ? '执行 Dry-run' : '开始导入' }}
            </el-button>
            <el-button
              :icon="Refresh"
              :disabled="running || !lastResult"
              @click="reset"
            >
              清空结果
            </el-button>
            <span v-if="running" class="running-tip">
              <el-icon class="is-loading"><Refresh /></el-icon>
              导入中，请勿关闭页面…
            </span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 结果卡片 -->
      <div v-if="lastResult" class="card">
        <div class="card-header">
          <div class="card-title">
            <el-icon class="title-icon"><CircleCheck /></el-icon>
            导入结果
            <el-tag
              :type="lastResult.dryRun ? 'info' : 'success'"
              effect="plain"
              size="small"
              style="margin-left: 8px"
            >
              {{ lastResult.dryRun ? 'Dry-run' : '已落库' }}
            </el-tag>
          </div>
          <span class="muted">完成时间：{{ lastRunAt }} · 耗时 {{ elapsedText }}</span>
        </div>

        <!-- 总览数字卡 -->
        <div class="overview-grid">
          <div class="ov-card">
            <div class="ov-icon"><el-icon><Files /></el-icon></div>
            <div class="ov-info">
              <div class="ov-num">{{ lastResult.importedCases }}</div>
              <div class="ov-label">
                {{ lastResult.dryRun ? '预计可导入' : '已入库（未发布）' }}
              </div>
            </div>
          </div>
          <div class="ov-card">
            <div class="ov-icon blue"><el-icon><Picture /></el-icon></div>
            <div class="ov-info">
              <div class="ov-num blue-text">{{ lastResult.appendedImages }}</div>
              <div class="ov-label">登记影像总数</div>
            </div>
          </div>
          <div class="ov-card">
            <div class="ov-icon">
              <el-icon><CircleClose /></el-icon>
            </div>
            <div class="ov-info">
              <div class="ov-num">{{ lastResult.skippedCases }}</div>
              <div class="ov-label">跳过 / 已存在</div>
            </div>
          </div>
          <div class="ov-card warn-card" @click="goIncomplete">
            <div class="ov-icon orange"><el-icon><WarningFilled /></el-icon></div>
            <div class="ov-info">
              <div class="ov-num orange-text">{{ lastResult.incompleteCases }}</div>
              <div class="ov-label">影像不完整（点击查看）</div>
            </div>
          </div>
        </div>

        <div v-if="!lastResult.dryRun" class="actions" style="margin-bottom: 14px">
          <el-button type="primary" @click="goCaseLibrary">
            前往病例库完善金标准 / 加入实训
          </el-button>
        </div>

        <!-- DR 分级分布 -->
        <div class="distrib-card">
          <div class="sub-title">DR 分级分布</div>
          <div v-if="gradeRows.length" class="grade-grid">
            <div v-for="r in gradeRows" :key="r.grade" class="grade-cell">
              <div class="g-num">{{ r.count }}</div>
              <div class="g-label">{{ r.grade }} 级</div>
            </div>
          </div>
          <div v-else class="empty">本批次无分级数据</div>
        </div>

        <!-- 样本病例编号 -->
        <div v-if="sampleCaseSns.length" class="sample-card">
          <div class="sub-title">样本病例编号（前 {{ sampleCaseSns.length }} 例）</div>
          <div class="sn-list">
            <el-tag
              v-for="sn in sampleCaseSns"
              :key="sn"
              type="primary"
              effect="plain"
              size="small"
            >
              {{ sn }}
            </el-tag>
          </div>
          <div class="actions">
            <el-button
              v-if="!lastResult.dryRun"
              type="primary"
              link
              @click="goCaseLibrary"
            >
              前往病例库完善金标准 / 加入实训 →
            </el-button>
            <el-button type="primary" link @click="goIncomplete">
              查看影像不完整列表 →
            </el-button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 18px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
  display: flex;
  align-items: center;
  gap: 6px;
}
.title-icon {
  color: #1677ff;
}
.muted {
  color: #86909c;
  font-size: 12px;
  font-weight: 400;
}
.hint {
  margin-top: 6px;
  color: #86909c;
  font-size: 12px;
}
.hint code,
.probe-meta code {
  background: #f2f3f5;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.flow-alert {
  margin-bottom: 18px;
}
.probe-meta {
  margin-top: 6px;
}

.form {
  margin-top: 4px;
}
.running-tip {
  margin-left: 12px;
  color: #1677ff;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.running-tip .is-loading {
  animation: rotating 1.5s linear infinite;
}
@keyframes rotating {
  to {
    transform: rotate(360deg);
  }
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}
.ov-card {
  background: #fafbfc;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.ov-card.warn-card {
  cursor: pointer;
  transition: 0.2s;
}
.ov-card.warn-card:hover {
  border-color: #ff7d00;
  background: #fff7e6;
}
.ov-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  font-size: 20px;
  background: #eef4ff;
  color: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ov-icon.blue {
  background: rgba(22, 119, 255, 0.12);
  color: #1677ff;
}
.ov-icon.orange {
  background: rgba(255, 125, 0, 0.12);
  color: #ff7d00;
}
.ov-info .ov-num {
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1.2;
}
.ov-info .ov-label {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.blue-text {
  color: #1677ff;
}
.orange-text {
  color: #ff7d00;
}

.sub-title {
  font-size: 13px;
  font-weight: 600;
  color: #4e5969;
  margin-bottom: 10px;
}
.distrib-card {
  background: #fafbfc;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
}
.grade-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 8px;
}
.grade-cell {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 4px;
  text-align: center;
}
.g-num {
  font-size: 18px;
  font-weight: 700;
  color: #1677ff;
}
.g-label {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.empty {
  padding: 12px 0;
  text-align: center;
  color: #c9cdd4;
  font-size: 13px;
}

.sample-card {
  background: #fafbfc;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 14px 16px;
}
.sn-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.actions {
  margin-top: 4px;
}

@media (max-width: 1280px) {
  .overview-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.backfill-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.backfill-result {
  margin-top: 8px;
}
</style>
