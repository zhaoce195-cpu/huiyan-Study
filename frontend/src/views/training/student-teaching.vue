<script setup lang="ts">
/**
 * 教师演示病例（学员端）
 * - 列出可见的临时分享 + 已入库教学病例
 * - 学员仅可查看脱敏数据 + 点击实训
 * - 已入库的可走练习流程；临时分享仅用于查看（脱敏只读）
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, View, Pointer } from '@element-plus/icons-vue'
import { PracticeApi, TeachingApi } from '@/api'
import TeachingDemoBody from './components/TeachingDemoBody.vue'

type StudentCase = TeachingApi.StudentCase

const router = useRouter()

const list = ref<StudentCase[]>([])
const loading = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const fetchList = async () => {
  loading.value = true
  try {
    const r = await TeachingApi.getStudentCases({
      page: pagination.page,
      pageSize: pagination.pageSize,
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

const detailVisible = ref(false)
const detail = ref<StudentCase | null>(null)
const detailLoading = ref(false)
const showDetail = async (row: StudentCase) => {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await TeachingApi.getStudentCaseDetail(row.id)
  } catch {
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

const onPractice = async (row: StudentCase) => {
  if (!row.teachingCaseId) {
    ElMessage.warning('该临时演示病例暂不支持启动正式练习，可点击查看进入只读阅片')
    return
  }
  try {
    const r = await PracticeApi.startPractice({
      caseId: row.teachingCaseId,
      mode: 'SELECTED',
    })
    router.push({
      path: '/training/practice/workstation',
      query: { sessionId: String(r.id), caseId: String(row.teachingCaseId) },
    })
  } catch {
    /* 已弹错误 */
  }
}

onMounted(fetchList)
</script>

<template>
  <div class="student-teaching-page">
    <header class="page-head">
      <div class="head-left">
        <h2>教师演示病例</h2>
        <div class="muted">带教按图讲解：先看什么、标准结论、图上的病灶（共 {{ pagination.total }} 份）</div>
      </div>
      <div class="head-right">
        <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
      </div>
    </header>

    <div v-loading="loading" class="case-grid">
      <el-empty v-if="!loading && list.length === 0" description="暂无演示病例" />

      <div v-for="c in list" :key="c.id" class="case-card">
        <div class="card-head">
          <el-tag size="small" :type="c.shareType === 'PERMANENT' ? 'primary' : 'warning'" effect="plain">
            {{ c.shareType === 'PERMANENT' ? '入库教学' : '教师演示' }}
          </el-tag>
          <span v-if="c.expiredAt && c.shareType === 'TEMPORARY'" class="muted small">
            到期：{{ c.expiredAt }}
          </span>
        </div>
        <div class="card-title">{{ c.title || '教学病例' }}</div>
        <div class="meta-line">
          <span class="muted small">{{ c.teacherName ? `${c.teacherName} 老师` : '—' }}</span>
          <span v-if="c.categoryText || c.category" class="dot">·</span>
          <span v-if="c.categoryText || c.category" class="muted small">{{ c.categoryText || c.category }}</span>
          <span v-if="c.difficultyText || c.difficulty" class="dot">·</span>
          <span v-if="c.difficultyText || c.difficulty" class="muted small">{{ c.difficultyText || c.difficulty }}</span>
        </div>
        <div class="patient-line">
          <span>{{ c.patientGender === 'M' ? '男' : c.patientGender === 'F' ? '女' : '未知' }}</span>
          <span v-if="c.patientAge" class="dot">·</span>
          <span v-if="c.patientAge">{{ c.patientAge }} 岁</span>
          <span class="dot">·</span>
          <span class="muted small">影像 {{ c.imageCount }} 张</span>
        </div>
        <div v-if="c.goldGradeText" class="grade">{{ c.goldGradeText }}</div>
        <div v-if="c.teachingPoints" class="desc multiline">
          <span class="kicker">先看</span>{{ c.teachingPoints }}
        </div>
        <div v-else-if="c.goldDiagnosis" class="desc multiline">{{ c.goldDiagnosis }}</div>
        <div v-else class="desc">这份分享还没有带教讲解</div>

        <div class="card-actions">
          <el-button size="small" :icon="View" @click="showDetail(c)">查看详情</el-button>
          <el-button
            v-if="c.teachingCaseId"
            type="primary"
            size="small"
            :icon="Pointer"
            @click="onPractice(c)"
          >
            开始实训
          </el-button>
        </div>
      </div>
    </div>

    <div v-if="pagination.total > pagination.pageSize" class="pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchList"
        @current-change="fetchList"
      />
    </div>

    <!-- 详情对话框（只读） -->
    <el-dialog v-model="detailVisible" :title="detail?.title || '演示病例'" width="920">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="hint">
            <el-tag size="small" type="info">教学演示</el-tag>
            <span class="who">
              {{ detail.patientGender === 'M' ? '男' : detail.patientGender === 'F' ? '女' : '未知' }}
              · {{ detail.patientAge ?? '—' }} 岁
              · {{ detail.teacherName ? `${detail.teacherName} 老师` : '带教' }}
            </span>
          </div>
          <TeachingDemoBody :source="detail" />
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.student-teaching-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 28px 36px;
}
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 12px;
  flex-wrap: wrap;
}
.head-left h2 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #1e293b; }
.head-left .muted { color: #475569; font-size: 13px; }

.case-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
  min-height: 200px;
}
.case-card {
  background: #181a20;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.case-card:hover {
  border-color: #4091ff;
  box-shadow: 0 4px 18px rgba(64, 145, 255, 0.12);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.card-title {
  font-size: 15px;
  font-weight: 700;
  color: #e5e6eb;
}
.meta-line, .patient-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #c9cdd4;
}
.dot { color: #aeb6c2; }
.grade { font-size: 13px; font-weight: 700; color: #9ec1ff; }
.kicker {
  display: inline-block;
  margin-right: 6px;
  padding: 0 6px;
  border-radius: 4px;
  background: #1d3a6e;
  color: #d6e4ff;
  font-size: 12px;
}
.desc {
  font-size: 13px;
  color: #d5dae3;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px dashed #2a2a2a;
}

.muted { color: #86909c; }
.muted.small { font-size: 11px; }

.pagination { margin-top: 16px; display: flex; justify-content: center; }
.multiline { white-space: pre-wrap; word-break: break-word; }

.detail-body { display: flex; flex-direction: column; gap: 12px; }
.detail-body .hint {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f9ff;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e6effe;
}
.who { color: #1d2129; font-size: 13px; }
</style>
