<script setup lang="ts">
/**
 * 教师演示病例（学员端）
 * - 列出可见的临时分享 + 已入库教学病例
 * - 学员仅可查看脱敏数据 + 点击实训
 * - 已入库的可走练习流程；临时分享仅用于查看（脱敏只读）
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, View, Pointer } from '@element-plus/icons-vue'
import { PracticeApi, TeachingApi } from '@/api'

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

const flatImages = computed(() => {
  if (!detail.value?.imagePaths) return []
  const out: string[] = []
  const sides: ('OD' | 'OS' | 'OU')[] = ['OD', 'OS', 'OU']
  for (const s of sides) {
    const arr = (detail.value.imagePaths as any)[s] || []
    if (Array.isArray(arr)) out.push(...arr)
  }
  return out
})

onMounted(fetchList)
</script>

<template>
  <div class="student-teaching-page">
    <header class="page-head">
      <div class="head-left">
        <h2>教师演示病例</h2>
        <div class="muted">由带教医师分享 / 入库的脱敏教学病例（共 {{ pagination.total }} 份）</div>
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
          <span v-if="c.category" class="dot">·</span>
          <span v-if="c.category" class="muted small">{{ c.category }}</span>
          <span v-if="c.difficulty" class="dot">·</span>
          <span v-if="c.difficulty" class="muted small">{{ c.difficulty }}</span>
        </div>
        <div class="patient-line">
          <span>{{ c.patientGender === 'M' ? '男' : c.patientGender === 'F' ? '女' : '未知' }}</span>
          <span v-if="c.patientAge" class="dot">·</span>
          <span v-if="c.patientAge">{{ c.patientAge }} 岁</span>
          <span class="dot">·</span>
          <span class="muted small">影像 {{ c.imageCount }} 张</span>
        </div>
        <div v-if="c.description" class="desc multiline">{{ c.description }}</div>

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
    <el-dialog v-model="detailVisible" :title="detail?.title || '病例详情'" width="780">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="hint">
            <el-tag size="small" type="info">教学脱敏病例</el-tag>
            <span class="muted small" style="margin-left: 8px">
              已自动隐藏患者隐私信息，仅展示医学教学相关数据
            </span>
          </div>

          <el-descriptions :column="2" border size="small" style="margin-top: 12px">
            <el-descriptions-item label="性别 / 年龄">
              {{ detail.patientGender === 'M' ? '男' : detail.patientGender === 'F' ? '女' : '未知' }}
              · {{ detail.patientAge ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="病例类别">
              {{ detail.category || '—' }} / {{ detail.difficulty || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="临床信息" :span="2">
              <span class="multiline">{{ detail.clinicalInfo || '—' }}</span>
            </el-descriptions-item>
            <el-descriptions-item v-if="detail.description" label="教学描述" :span="2">
              <span class="multiline">{{ detail.description }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="flatImages.length" class="images">
            <h4>影像资料 ({{ flatImages.length }})</h4>
            <div class="image-grid">
              <el-image
                v-for="(img, i) in flatImages"
                :key="i"
                :src="img"
                fit="cover"
                class="grid-thumb"
                :preview-src-list="flatImages"
                :initial-index="i"
                preview-teleported
              >
                <template #error>
                  <div class="thumb-error">影像加载失败</div>
                </template>
              </el-image>
            </div>
          </div>
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
.head-left h2 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #e5e6eb; }
.head-left .muted { color: #86909c; font-size: 13px; }

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
.dot { color: #4e5969; }
.desc {
  font-size: 12px;
  color: #86909c;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
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
  background: #f5f9ff;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e6effe;
}
.detail-body h4 {
  margin: 12px 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
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
</style>
