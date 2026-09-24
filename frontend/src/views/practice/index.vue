<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ExamApi, PracticeApi } from '@/api'
import type { ExamPaper } from '@/api/exam'
import { useUserStore } from '@/stores/user'
import { isDrGradeNotApplicable } from '@/utils/filter-presets'
import { actorLabel } from '@/utils/actor'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

type TabName = 'pick' | 'history' | 'stats'

const isStudent = computed(() => userStore.isTrainee)
const isTeacher = computed(() => userStore.isDoctor || userStore.isAdmin)

const activeTab = ref<TabName>('pick')

/* ========== 随机/自选 ========== */

const filterForm = ref({
  category: '',
  difficulty: '',
  drLevel: undefined as number | undefined,
  excludeDone: true
})

/**
 * DR 分级只对糖网和正常眼底有意义，AMD / 青光眼这些病种库里存的是「不适用」。
 * 选了黄斑还让人挑 DR 等级，只会得到一个永远抽不到病例的组合
 *（用户测试报告 D-3）。禁用并清空。
 */
const drLevelDisabled = computed(() => isDrGradeNotApplicable(filterForm.value.category))
watch(drLevelDisabled, (off) => {
  if (off) filterForm.value.drLevel = undefined
})

const randomCase = ref<PracticeApi.CaseBriefForPractice | null>(null)
/** 同一地址挂在左右眼两栏时，卡片只显示一张 */
const cardImages = computed(() => {
  const seen = new Set<string>()
  const out: string[] = []
  for (const img of randomCase.value?.images || []) {
    if (!img || seen.has(img)) continue
    seen.add(img)
    out.push(img)
  }
  return out
})
const randomLoading = ref(false)
const clearPickFilters = () => {
  filterForm.value.category = ''
  filterForm.value.difficulty = ''
  filterForm.value.drLevel = undefined
  filterForm.value.excludeDone = true
  fetchRandom()
}

const fetchRandom = async () => {
  randomLoading.value = true
  try {
    randomCase.value = await PracticeApi.getRandomCase({
      category: filterForm.value.category || undefined,
      difficulty: filterForm.value.difficulty || undefined,
      drLevel: filterForm.value.drLevel,
      excludeDone: filterForm.value.excludeDone
    })
  } catch (err: any) {
    randomCase.value = null
    if (err?.code !== 1000) ElMessage.warning('暂未匹配到合适病例，请调整筛选')
  } finally {
    randomLoading.value = false
  }
}

const startPractice = async (mode: PracticeApi.PracticeMode, caseId: number) => {
  try {
    const rec = await PracticeApi.startPractice({ caseId, mode })
    router.push({
      path: '/practice/workstation',
      query: { sessionId: String(rec.id), caseId: String(caseId) }
    })
  } catch {
    /* ignore */
  }
}

const exams = ref<ExamPaper[]>([])
const examStartingId = ref(0)
const fetchExams = async () => {
  if (!isStudent.value) return
  try {
    exams.value = (await ExamApi.listExams()) || []
  } catch {
    exams.value = []
  }
}
const enterExam = async (paper: ExamPaper) => {
  examStartingId.value = paper.id
  try {
    const rec = await ExamApi.startExam(paper.id)
    router.push({
      path: '/practice/workstation',
      query: {
        sessionId: String(rec.id),
        caseId: String(rec.caseId),
        ...(rec.answersOpen ? { view: 'report' } : {})
      }
    })
  } finally {
    examStartingId.value = 0
  }
}
const examActionText = (paper: ExamPaper) => {
  if (paper.status === 'CLOSED') return '查看成绩'
  if (paper.mineStatus === 'DOING') return '继续考试'
  if (paper.mineStatus === 'HANDED') return '等待收卷'
  return '进入考试'
}

/* ========== 自选病例 — 通过病例浏览页跳转 ========== */
const goSelectFromBrowse = () => {
  router.push({ path: '/case-browse', query: { mode: 'practice' } })
}

/* ========== 历史台账 ========== */

const listLoading = ref(false)
const listQuery = ref<PracticeApi.PracticeListQuery>({
  page: 1,
  pageSize: 20,
  status: '',
  isPassed: undefined
})
const clearHistoryFilters = () => {
  listQuery.value.status = ''
  listQuery.value.isPassed = undefined
  listQuery.value.page = 1
  fetchList()
}

const listData = ref<PracticeApi.PracticeRecord[]>([])
const listTotal = ref(0)

const fetchList = async () => {
  listLoading.value = true
  try {
    const res = await PracticeApi.getPracticeList({
      ...listQuery.value,
      status: (listQuery.value.status || undefined) as any
    })
    listData.value = res.list || []
    listTotal.value = res.total || 0
  } catch {
    listData.value = []
    listTotal.value = 0
  } finally {
    listLoading.value = false
  }
}

const onPageChange = (p: number) => {
  listQuery.value.page = p
  fetchList()
}
const onSizeChange = (s: number) => {
  listQuery.value.pageSize = s
  listQuery.value.page = 1
  fetchList()
}

const continueDraft = (rec: PracticeApi.PracticeRecord) => {
  router.push({
    path: '/practice/workstation',
    query: { sessionId: String(rec.id), caseId: String(rec.caseId) }
  })
}

const viewReport = (rec: PracticeApi.PracticeRecord) => {
  router.push({
    path: '/practice/workstation',
    query: { sessionId: String(rec.id), caseId: String(rec.caseId), view: 'report' }
  })
}

const removeRecord = async (rec: PracticeApi.PracticeRecord) => {
  try {
    await ElMessageBox.confirm(`确认删除这条练习记录？(${rec.caseNo})`, '提示', {
      type: 'warning'
    })
  } catch {
    return
  }
  await PracticeApi.deletePractice(rec.id)
  fetchList()
}

const statusTagType = (s: PracticeApi.PracticeStatus) => {
  if (s === 'DRAFT') return 'info'
  return 'success'
}
const statusText = (s: PracticeApi.PracticeStatus) =>
  s === 'DRAFT' ? '草稿' : '已评分'

/* ========== 统计 ========== */

const statsLoading = ref(false)
const stats = ref<PracticeApi.PracticeStats | null>(null)

const fetchStats = async (target: 'me' | 'all' = 'me') => {
  statsLoading.value = true
  try {
    if (target === 'all') {
      stats.value = await PracticeApi.getAllStats()
    } else {
      stats.value = await PracticeApi.getMyStats()
    }
  } catch {
    stats.value = null
  } finally {
    statsLoading.value = false
  }
}

/* ========== 初始化 ========== */
onMounted(async () => {
  const tab = String(route.query.tab || '')
  if (tab === 'history') {
    activeTab.value = 'history'
  }
  await fetchRandom()
  fetchExams()
  fetchList()
  fetchStats(isTeacher.value ? 'all' : 'me')
})

</script>

<template>
  <div class="practice-page">
    <main class="page-body">
      <el-tabs v-model="activeTab" class="practice-tabs">
        <!-- 选病例 -->
        <el-tab-pane label="选病例" name="pick">
          <div class="pick-section">
            <el-card v-if="isStudent" class="filter-card exam-entry" shadow="never">
              <template #header>
                <span class="card-title">正式考试</span>
              </template>
              <div v-if="exams.length" class="exam-list">
                <div v-for="paper in exams" :key="paper.id" class="exam-row">
                  <div>
                    <strong>{{ paper.title }}</strong>
                    <div class="exam-meta">
                      {{ paper.questionCount }} 题 · {{ paper.durationMinutes }} 分钟 · 合格线
                      {{ paper.passScore }} 分 ·
                      {{ paper.allowBack ? '可以返回上一题' : '不能返回上一题' }}
                      <span v-if="paper.status === 'CLOSED'"> · 已收卷</span>
                    </div>
                  </div>
                  <el-button
                    type="warning"
                    :loading="examStartingId === paper.id"
                    :disabled="paper.status === 'OPEN' && paper.mineStatus === 'HANDED'"
                    @click="enterExam(paper)"
                  >
                    {{ examActionText(paper) }}
                  </el-button>
                </div>
              </div>
              <el-empty v-else description="老师还没有发布考试" :image-size="64" />
            </el-card>
            <el-card v-else class="filter-card" shadow="never">
              <span class="card-title">正式考试在侧栏「正式考试」里发布。这里仍是平时练习。</span>
            </el-card>
            <el-card class="filter-card" shadow="never">
              <template #header>
                <span class="card-title">随机抽取一份病例</span>
              </template>
              <el-form :inline="true" :model="filterForm" size="default" label-width="72px">
                <el-form-item label="病种">
                  <el-select
                    v-model="filterForm.category"
                    placeholder="全部病种"
                    clearable
                    style="width: 180px"
                  >
                    <el-option
                      v-for="o in PracticeApi.CATEGORY_FILTERS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="难度">
                  <el-select
                    v-model="filterForm.difficulty"
                    placeholder="全部难度"
                    clearable
                    style="width: 140px"
                  >
                    <el-option
                      v-for="o in PracticeApi.DIFFICULTY_FILTERS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="DR 级">
                  <el-select
                    v-model="filterForm.drLevel"
                    :placeholder="drLevelDisabled ? '该病种不适用' : '全部'"
                    :disabled="drLevelDisabled"
                    :title="drLevelDisabled ? 'DR 分级仅适用于糖网与正常眼底' : ''"
                    clearable
                    style="width: 160px"
                  >
                    <el-option
                      v-for="o in PracticeApi.DR_GRADE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="Number(o.value)"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-checkbox v-model="filterForm.excludeDone">
                    排除已通过病例
                  </el-checkbox>
                </el-form-item>
                <el-form-item>
                  <el-button @click="clearPickFilters">清除</el-button>
                  <el-button type="primary" :loading="randomLoading" @click="fetchRandom">
                    换一份
                  </el-button>
                  <el-button @click="goSelectFromBrowse">
                    去病例库自选
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>

            <el-card v-if="randomCase" class="case-card" shadow="never">
              <div class="case-card-body">
                <div class="case-thumbs">
                  <el-image
                    v-for="(img, i) in cardImages.slice(0, 3)"
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
                <div class="case-info">
                  <h2>{{ randomCase.title || randomCase.caseNo }}</h2>
                  <div class="case-meta">
                    <el-tag size="small">{{ randomCase.caseNo }}</el-tag>
                    <el-tag size="small" type="info">{{ randomCase.categoryText }}</el-tag>
                    <el-tag size="small" type="warning">{{ randomCase.difficultyText }}</el-tag>
                    <!-- 盲训态：作答前不显示正确分级（报告 P0） -->
                    <el-tag v-if="randomCase.drGradeText" size="small" type="success">
                      {{ randomCase.drGradeText }}
                    </el-tag>
                    <el-tag v-else size="small" type="info" effect="plain">分级待判读</el-tag>
                    <el-tag size="small" effect="plain">
                      共 {{ cardImages.length }} 张影像
                    </el-tag>
                  </div>
                  <div class="pass-line">
                    通过分数线：<strong>{{ randomCase.passScore }}</strong> 分。
                    平时练习可以逐则看提示。正式考试由老师组卷，收卷后才显示答案。
                  </div>
                  <div class="case-actions">
                    <el-button
                      type="primary"
                      size="large"
                      @click="startPractice('RANDOM', randomCase.caseId)"
                    >
                      学习这例
                    </el-button>
                    <el-button size="large" @click="fetchRandom">换一份</el-button>
                  </div>
                </div>
              </div>
            </el-card>

            <el-empty v-else-if="!randomLoading" description="暂未匹配到合适病例，请调整筛选条件" />
          </div>
        </el-tab-pane>

        <!-- 历史台账 -->
        <el-tab-pane label="练习台账" name="history">
          <div class="history-section">
            <el-card class="filter-card" shadow="never">
              <el-form :inline="true" :model="listQuery" size="default" label-width="64px">
                <el-form-item label="状态">
                  <el-select
                    v-model="listQuery.status"
                    placeholder="全部"
                    clearable
                    style="width: 140px"
                  >
                    <el-option label="草稿" value="DRAFT" />
                    <el-option label="已评分" value="SUBMITTED" />
                    <el-option label="已评分（较早记录）" value="REVIEWED" />
                  </el-select>
                </el-form-item>
                <el-form-item label="是否通过">
                  <el-select
                    v-model="listQuery.isPassed"
                    placeholder="全部"
                    clearable
                    style="width: 120px"
                  >
                    <el-option label="通过" :value="true" />
                    <el-option label="未通过" :value="false" />
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-button @click="clearHistoryFilters">清除</el-button>
                  <el-button type="primary" @click="fetchList">查询</el-button>
                </el-form-item>
              </el-form>
            </el-card>

            <el-table
              v-loading="listLoading"
              :data="listData"
              border
              stripe
              size="default"
              style="width: 100%; margin-top: 12px"
            >
              <el-table-column prop="caseNo" label="病例编号" min-width="120" />
              <el-table-column prop="caseTitle" label="病例" min-width="160" />
              <el-table-column prop="caseDifficulty" label="难度" width="80" />
              <el-table-column label="方式" width="88">
                <template #default="{ row }">
                  {{ row.attemptKind === 'EXAM' ? '考试' : '练习' }}
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="statusTagType(row.status)">
                    {{ statusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="得分" width="120">
                <template #default="{ row }">
                  <strong v-if="row.answersOpen">
                    {{ Number(row.scoreTotal || 0).toFixed(1) }}
                  </strong>
                  <span v-else-if="row.attemptKind === 'EXAM' && row.status !== 'DRAFT'">
                    交卷后公布
                  </span>
                  <span v-else style="color: #c9cdd4">—</span>
                </template>
              </el-table-column>
              <el-table-column label="是否通过" width="90">
                <template #default="{ row }">
                  <el-tag
                    v-if="row.answersOpen"
                    :type="row.isPassed ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ row.isPassed ? '通过' : '未通过' }}
                  </el-tag>
                  <span v-else style="color: #c9cdd4">—</span>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="90">
                <template #default="{ row }">
                  {{ row.durationSeconds ? Math.round(row.durationSeconds / 60) + '分' : '—' }}
                </template>
              </el-table-column>
              <el-table-column prop="submittedAt" label="提交时间" width="170" />
              <el-table-column label="点评人" min-width="160">
                <template #default="{ row }">
                  <span v-if="row.status === 'DRAFT'" style="color: #c9cdd4">—</span>
                  <template v-else>
                    <span v-if="row.teacherName">{{ actorLabel(row.teacherName, row.teacherRole) }}</span>
                    <span v-else style="color: #86909c">系统评分</span>
                    <div v-if="row.teacherComment" style="color: #4e5969; font-size: 12px">
                      {{ row.teacherComment }}
                    </div>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === 'DRAFT'"
                    size="small"
                    type="primary"
                    @click="continueDraft(row)"
                  >
                    继续
                  </el-button>
                  <el-button
                    v-else
                    size="small"
                    type="primary"
                    @click="viewReport(row)"
                  >
                    查看报告
                  </el-button>
                  <el-button
                    v-if="row.status === 'DRAFT' || isTeacher"
                    size="small"
                    type="danger"
                    plain
                    @click="removeRecord(row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-pagination
              :current-page="listQuery.page"
              :page-size="listQuery.pageSize"
              :total="listTotal"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next, jumper"
              style="margin-top: 14px; justify-content: flex-end; display: flex"
              @current-change="onPageChange"
              @size-change="onSizeChange"
            />
          </div>
        </el-tab-pane>

        <!-- 统计 -->
        <el-tab-pane label="数据统计" name="stats">
          <div class="stats-section" v-loading="statsLoading">
            <div class="stats-toolbar">
              <span class="muted">{{ isTeacher ? '全班级统计' : '我的练习统计' }}</span>
              <div class="actions">
                <el-button v-if="isTeacher" size="small" @click="fetchStats('me')">
                  我的
                </el-button>
                <el-button v-if="isTeacher" size="small" type="primary" @click="fetchStats('all')">
                  全班级
                </el-button>
                <el-button v-if="isStudent" size="small" type="primary" @click="fetchStats('me')">
                  刷新
                </el-button>
              </div>
            </div>

            <div v-if="stats" class="stats-grid">
              <div class="stat-card">
                <div class="stat-label">练习次数</div>
                <div class="stat-value">{{ stats.submittedSessions }}</div>
                <div class="stat-sub">未交卷 {{ Math.max(0, stats.totalSessions - stats.submittedSessions) }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">完成病例</div>
                <div class="stat-value">{{ stats.completedCases }}</div>
                <div class="stat-sub">已交卷练习和阅片，同一病例只计一例</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">通过率</div>
                <div class="stat-value">
                  {{ (stats.passRate * 100).toFixed(1) }}<small>%</small>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">平均成绩</div>
                <div class="stat-value">{{ stats.avgScore.toFixed(1) }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">平均 IoU</div>
                <div class="stat-value">{{ stats.avgIou.toFixed(2) }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-label">学时</div>
                <div class="stat-value">
                  {{ Math.round(stats.totalDuration / 60) }}<small>分钟</small>
                </div>
                <div class="stat-sub">只计已交卷练习</div>
              </div>
            </div>

            <el-card v-if="stats?.weakLabels?.length" shadow="never" class="weak-card">
              <template #header>
                <span class="card-title">薄弱标签 Top {{ stats.weakLabels.length }}</span>
              </template>
              <el-table :data="stats.weakLabels" border size="small">
                <el-table-column prop="label" label="病灶标签" />
                <el-table-column prop="missed" label="漏标次数" width="100" />
                <el-table-column prop="falsePositive" label="误标次数" width="100" />
                <el-table-column label="平均 IoU" width="120">
                  <template #default="{ row }">
                    {{ row.avgIou.toFixed(2) }}
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-empty v-else-if="!stats" description="暂无统计数据" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </main>
  </div>
</template>

<style scoped>
.practice-page {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}
.page-header {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e5e6eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
.page-header .left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}
.user-mini {
  color: #4e5969;
  font-size: 13px;
}
.page-body {
  flex: 1;
  padding: 18px 24px 30px;
  max-width: none;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}
.practice-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
}
.card-title {
  font-weight: 600;
  font-size: 14px;
}
.filter-card {
  border-radius: 8px;
}

.case-card {
  margin-top: 14px;
  border-radius: 8px;
}
.case-card-body {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.case-thumbs {
  display: grid;
  grid-template-columns: 220px;
  gap: 8px;
  flex-shrink: 0;
}
.thumb {
  width: 220px;
  height: 160px;
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
  font-size: 12px;
  background: #1d2129;
}
.case-info {
  flex: 1;
}
.case-info h2 {
  margin: 0 0 12px;
  font-size: 22px;
  color: #1d2129;
}
.case-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.pass-line {
  font-size: 13px;
  color: #4e5969;
  margin-bottom: 16px;
}
.pass-line strong {
  color: #f53f3f;
  font-size: 16px;
}
.case-actions {
  display: flex;
  gap: 12px;
}
.exam-entry {
  margin-bottom: 12px;
}
.exam-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
}
.exam-row + .exam-row {
  border-top: 1px solid #f2f3f5;
}
.exam-meta {
  margin-top: 4px;
  color: #86909c;
  font-size: 13px;
}

.history-section,
.stats-section {
  display: flex;
  flex-direction: column;
}
.stats-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.muted {
  color: #86909c;
  font-size: 13px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 18px 20px;
}
.stat-label {
  font-size: 13px;
  color: #86909c;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #1d2129;
  margin-top: 6px;
}
.stat-value small {
  font-size: 13px;
  color: #86909c;
  margin-left: 4px;
  font-weight: 500;
}
.stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
}
.weak-card {
  border-radius: 8px;
}
.review-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}
.review-comment {
  font-size: 12px;
  color: #4e5969;
  line-height: 1.4;
}
@media (max-width: 1080px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .case-card-body {
    flex-direction: column;
  }
}
</style>
