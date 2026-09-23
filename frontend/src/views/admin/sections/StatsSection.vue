<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh, Search, DataAnalysis, User, Document, Trophy } from '@element-plus/icons-vue'
import { CommonApi } from '@/api'

type TrainingOverview = CommonApi.TrainingOverview
type StudyHoursItem = CommonApi.StudyHoursItem

const props = defineProps<{
  /** TEACHER/ADMIN 才可查看 */
  canManage: boolean
}>()

/* ========== 全院培训统计 ========== */

const overview = ref<TrainingOverview | null>(null)
const overviewLoading = ref(false)

const fetchOverview = async () => {
  if (!props.canManage) return
  overviewLoading.value = true
  try {
    overview.value = await CommonApi.getTrainingOverview()
  } catch {
    overview.value = null
  } finally {
    overviewLoading.value = false
  }
}

const passRatePercent = computed(() => {
  const r = overview.value?.passRate || 0
  return Math.round(r * 1000) / 10
})
const avgIouPercent = computed(() => {
  const r = overview.value?.avgIou || 0
  return Math.round(r * 1000) / 10
})

const maxByDifficulty = computed(() => {
  const arr = overview.value?.byDifficulty || []
  return arr.reduce((m, it) => Math.max(m, it.value), 1)
})
const maxByDrGrade = computed(() => {
  const arr = overview.value?.byDrGrade || []
  return arr.reduce((m, it) => Math.max(m, it.value), 1)
})

/* ========== 学员学时汇总 ========== */

const studyList = ref<StudyHoursItem[]>([])
const studyTotal = ref(0)
const studyLoading = ref(false)
const studyFilter = reactive({ keyword: '' })
const studyPagination = reactive({ page: 1, pageSize: 50 })

const fetchStudy = async () => {
  if (!props.canManage) return
  studyLoading.value = true
  try {
    const res = await CommonApi.getStudyHours({
      keyword: studyFilter.keyword || undefined,
      page: studyPagination.page,
      pageSize: studyPagination.pageSize
    })
    studyList.value = res?.list || []
    studyTotal.value = res?.total || 0
  } catch {
    studyList.value = []
    studyTotal.value = 0
  } finally {
    studyLoading.value = false
  }
}

const onStudyFilter = () => {
  studyPagination.page = 1
  fetchStudy()
}

const clearStudyFilter = () => {
  studyFilter.keyword = ''
  onStudyFilter()
}

const refresh = () => {
  fetchOverview()
  fetchStudy()
}

onMounted(refresh)
</script>

<template>
  <div class="stats-section">
    <div v-if="!canManage" class="card">
      <el-alert
        title="当前账号无统计报表查看权限"
        type="warning"
        description="仅带教医师（TEACHER）和平台管理员（ADMIN）可查看统计报表。"
        :closable="false"
        show-icon
      />
    </div>

    <template v-else>
      <!-- 总览数字卡 -->
      <div class="overview-grid" v-loading="overviewLoading">
        <div class="ov-card">
          <div class="ov-icon"><el-icon><User /></el-icon></div>
          <div class="ov-info">
            <div class="ov-num">{{ overview?.totalUsers || 0 }}</div>
            <div class="ov-label">参训学员</div>
          </div>
        </div>
        <div class="ov-card">
          <div class="ov-icon"><el-icon><Document /></el-icon></div>
          <div class="ov-info">
            <div class="ov-num">{{ overview?.totalCases || 0 }}</div>
            <div class="ov-label">病例总数</div>
          </div>
        </div>
        <div class="ov-card">
          <div class="ov-icon"><el-icon><DataAnalysis /></el-icon></div>
          <div class="ov-info">
            <div class="ov-num">{{ overview?.totalRecords || 0 }}</div>
            <div class="ov-label">答卷总数</div>
          </div>
        </div>
        <div class="ov-card">
          <div class="ov-icon green"><el-icon><Trophy /></el-icon></div>
          <div class="ov-info">
            <div class="ov-num green-text">{{ avgIouPercent }}%</div>
            <div class="ov-label">平均 IoU</div>
          </div>
        </div>
        <div class="ov-card">
          <div class="ov-icon blue"><el-icon><Trophy /></el-icon></div>
          <div class="ov-info">
            <div class="ov-num blue-text">{{ passRatePercent }}%</div>
            <div class="ov-label">合格率（IoU ≥ 0.6）</div>
          </div>
        </div>
        <div class="ov-card refresh-card" @click="fetchOverview">
          <div class="ov-icon"><el-icon><Refresh /></el-icon></div>
          <div class="ov-info">
            <div class="ov-num small">点击刷新</div>
            <div class="ov-label">重新拉取统计</div>
          </div>
        </div>
      </div>

      <!-- 分布图表（柱状） -->
      <div class="distrib-grid" v-loading="overviewLoading">
        <div class="card">
          <div class="card-header">
            <div class="card-title">病例难度分布</div>
            <span class="muted">{{ overview?.byDifficulty?.length || 0 }} 类</span>
          </div>
          <div class="bar-list">
            <div
              v-for="it in overview?.byDifficulty || []"
              :key="it.label"
              class="bar-row"
            >
              <span class="bar-label">{{ it.label }}</span>
              <div class="bar-track">
                <div
                  class="bar-fill diff"
                  :style="{ width: ((it.value / maxByDifficulty) * 100).toFixed(1) + '%' }"
                ></div>
              </div>
              <span class="bar-value">{{ it.value }}</span>
            </div>
            <div v-if="!(overview?.byDifficulty?.length)" class="empty">暂无分布数据</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">DR 分级分布</div>
            <span class="muted">{{ overview?.byDrGrade?.length || 0 }} 级</span>
          </div>
          <div class="bar-list">
            <div
              v-for="it in overview?.byDrGrade || []"
              :key="it.label"
              class="bar-row"
            >
              <span class="bar-label">{{ it.label }}</span>
              <div class="bar-track">
                <div
                  class="bar-fill dr"
                  :style="{ width: ((it.value / maxByDrGrade) * 100).toFixed(1) + '%' }"
                ></div>
              </div>
              <span class="bar-value">{{ it.value }}</span>
            </div>
            <div v-if="!(overview?.byDrGrade?.length)" class="empty">暂无分布数据</div>
          </div>
        </div>
      </div>

      <!-- 学员学时汇总 -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            学员学时汇总
            <span class="muted ml8">共 {{ studyTotal }} 人</span>
          </div>
          <div class="card-actions">
            <el-input
              v-model="studyFilter.keyword"
              placeholder="搜索用户名 / 姓名"
              :prefix-icon="Search"
              clearable
              size="small"
              style="width: 220px"
              @change="onStudyFilter"
              @clear="onStudyFilter"
            />
            <el-button size="small" @click="clearStudyFilter">清除</el-button>
            <el-button :icon="Refresh" size="small" @click="fetchStudy">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="studyLoading" :data="studyList" size="small" stripe>
          <el-table-column type="index" label="#" width="56" />
          <el-table-column prop="username" label="账号" width="140" />
          <el-table-column prop="realName" label="姓名" width="120" />
          <el-table-column prop="department" label="科室" min-width="160">
            <template #default="{ row }">
              <span v-if="row.department">{{ row.department }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="学时（小时）" width="160" sortable :sort-by="(r: StudyHoursItem) => r.totalHours">
            <template #default="{ row }">
              <b>{{ row.totalHours.toFixed(2) }}</b>
              <span class="muted ml8">{{ row.totalSeconds }} 秒</span>
            </template>
          </el-table-column>
          <el-table-column label="练习次数" width="110" sortable :sort-by="(r: StudyHoursItem) => r.practiceCount" prop="practiceCount" />
          <el-table-column prop="caseCount" label="完成病例" width="120" sortable />
          <el-table-column label="平均成绩" width="110" sortable :sort-by="(r: StudyHoursItem) => r.avgScore">
            <template #default="{ row }">{{ row.avgScore.toFixed(1) }}</template>
          </el-table-column>
          <el-table-column label="平均 IoU" width="180" sortable :sort-by="(r: StudyHoursItem) => r.avgIou">
            <template #default="{ row }">
              <el-progress
                :percentage="Number((row.avgIou * 100).toFixed(1))"
                :stroke-width="8"
                :show-text="false"
                :color="row.avgIou >= 0.6 ? '#00b42a' : row.avgIou >= 0.4 ? '#ff7d00' : '#f53f3f'"
                style="width: 90px; display: inline-block; vertical-align: middle"
              />
              <span class="conf-num">{{ (row.avgIou * 100).toFixed(1) }}%</span>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty">{{ studyLoading ? '加载中…' : '暂无学员学时数据' }}</div>
          </template>
        </el-table>
        <div v-if="studyTotal > studyPagination.pageSize" class="pagination">
          <el-pagination
            v-model:current-page="studyPagination.page"
            v-model:page-size="studyPagination.pageSize"
            :total="studyTotal"
            :page-sizes="[20, 50, 100, 200]"
            background
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="fetchStudy"
            @current-change="fetchStudy"
          />
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
}
.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.muted {
  color: #86909c;
  font-size: 12px;
  font-weight: 400;
}
.ml8 {
  margin-left: 8px;
}
.empty {
  padding: 36px 0;
  text-align: center;
  color: #c9cdd4;
  font-size: 14px;
}
.pagination {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}
.ov-card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.ov-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  font-size: 22px;
  background: #eef4ff;
  color: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ov-icon.green {
  background: rgba(0, 180, 42, 0.12);
  color: #00b42a;
}
.ov-icon.blue {
  background: rgba(22, 119, 255, 0.12);
  color: #1677ff;
}
.ov-info .ov-num {
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1.2;
}
.ov-info .ov-num.small {
  font-size: 14px;
}
.ov-info .ov-label {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.green-text { color: #00b42a; }
.blue-text { color: #1677ff; }
.refresh-card {
  cursor: pointer;
  transition: 0.2s;
}
.refresh-card:hover {
  border-color: #1677ff;
  background: #f7faff;
}

.distrib-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.bar-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bar-row {
  display: grid;
  grid-template-columns: 110px 1fr 60px;
  gap: 10px;
  align-items: center;
  font-size: 13px;
}
.bar-label {
  color: #4e5969;
}
.bar-track {
  background: #f2f3f5;
  border-radius: 4px;
  height: 12px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #4091ff, #1677ff);
  transition: width 0.3s;
}
.bar-fill.dr {
  background: linear-gradient(90deg, #00b42a, #ff7d00, #f53f3f);
}
.bar-value {
  text-align: right;
  font-weight: 600;
  color: #1d2129;
}
.conf-num {
  margin-left: 6px;
  font-size: 12px;
  color: #4e5969;
  vertical-align: middle;
}

@media (max-width: 1280px) {
  .overview-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .distrib-grid {
    grid-template-columns: 1fr;
  }
}
</style>
