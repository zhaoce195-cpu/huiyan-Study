<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Picture, Promotion, Check } from '@element-plus/icons-vue'
import type { CaseBrowseApi } from '@/api'
import { useTrainingJoinStore } from '@/stores/training-join'

type Detail = CaseBrowseApi.CaseBrowseDetail

const props = defineProps<{
  visible: boolean
  loading: boolean
  data: Detail | null
  canArchive: boolean
  canEditGold?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'join-training', row: Detail): void
  (e: 'edit-gold', row: Detail): void
  (e: 'preview-images', images: string[]): void
}>()

const joinStore = useTrainingJoinStore()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const close = () => {
  dialogVisible.value = false
}

const onPreview = () => {
  const imgs = (props.data?.images || []).filter(Boolean)
  if (imgs.length === 0) {
    ElMessage.info('该病例暂无影像')
    return
  }
  emit('preview-images', imgs)
}

/* ========== 加入实训按钮态 ========== */
const joinedHere = computed(() => {
  if (!props.data) return false
  // 后端 isTrainCase 为权威源；本地 store 用于乐观更新及未刷新场景
  if (props.data.isTrainCase) return true
  return joinStore.isJoined(props.data.id)
})
const joiningHere = computed(() =>
  props.data ? joinStore.isJoining(props.data.id) : false
)
const joinDisabled = computed(() => {
  if (!props.data) return true
  if (props.data.archiveStatus === 'ARCHIVED') return true
  return joinedHere.value || joiningHere.value
})
const joinButtonText = computed(() => (joinedHere.value ? '已加入实训' : '加入实训'))

/* 转交父级真正发请求；父级在 store 上更新 loading / joined 状态，
   弹窗只读取 store —— 反馈即时同步，不重复发请求。 */
const onJoin = () => {
  if (!props.data) return
  if (props.data.archiveStatus === 'ARCHIVED') {
    ElMessage.warning('该病例已归档，无法加入实训')
    return
  }
  if (joinedHere.value) {
    ElMessage.info('该病例已在实训库中，无需重复添加')
    return
  }
  if (joiningHere.value) return
  emit('join-training', props.data)
}

const genderText = (g: string) => {
  if (g === 'M') return '男'
  if (g === 'F') return '女'
  return '未填写'
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="病例详情"
    width="780"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div v-loading="loading" class="case-detail">
      <template v-if="data">
        <!-- 头部信息 -->
        <div class="detail-header">
          <div class="title-line">
            <span class="case-no">{{ data.caseNo }}</span>
            <span class="title">{{ data.title || '—' }}</span>
            <el-tag
              :type="data.archiveStatus === 'ARCHIVED' ? 'info' : 'success'"
              size="small"
              effect="plain"
            >
              {{ data.archiveStatus === 'ARCHIVED' ? '已归档' : '在用' }}
            </el-tag>
            <el-tag
              v-if="!data.isPublished"
              type="warning"
              size="small"
              effect="plain"
            >
              草稿 · 未发布
            </el-tag>
            <el-tag
              v-else-if="data.isTrainCase"
              type="success"
              size="small"
              effect="dark"
            >
              已加入实训
            </el-tag>
          </div>
          <div class="meta-line">
            <el-tag size="small" effect="plain">{{ data.categoryText || data.category }}</el-tag>
            <el-tag size="small" type="warning" effect="plain">
              {{ data.drGradeText || (data.drLevel !== null && data.drLevel !== undefined ? `${data.drLevel} 级` : '作答后可见') }}
            </el-tag>
            <el-tag size="small" type="info" effect="plain">
              难度：{{ data.difficultyText || data.difficulty }}
            </el-tag>
            <span class="muted">影像 {{ data.imageCount }} 张</span>
          </div>
        </div>

        <!-- 描述区 -->
        <el-descriptions :column="2" border size="small" class="desc-block" title="患者信息">
          <el-descriptions-item label="姓名">
            <b v-if="data.patientName">{{ data.patientName }}</b>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="性别">
            {{ genderText(data.patientGender || 'U') }}
          </el-descriptions-item>
          <el-descriptions-item label="年龄">
            <span v-if="data.patientAge">{{ data.patientAge }} 岁</span>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="手机号">
            <span v-if="data.patientPhone" class="phone-text">
              {{ data.patientPhone }}
              <el-tag
                v-if="data.phoneVisible === false"
                size="small"
                type="info"
                effect="plain"
                style="margin-left: 6px"
              >已脱敏</el-tag>
            </span>
            <span v-else class="muted">无权限查看</span>
          </el-descriptions-item>
          <el-descriptions-item label="病例编号" :span="2">
            <span class="case-no">{{ data.caseNo }}</span>
            <span v-if="data.caseSn" class="case-sn">/ {{ data.caseSn }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-descriptions :column="2" border size="small" class="desc-block" title="病例与教学">
          <el-descriptions-item label="创建人">
            {{ data.creatorName || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="上传时间">
            {{ data.createdAt || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="病例描述" :span="2">
            <span v-if="data.description">{{ data.description }}</span>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="临床信息" :span="2">
            <span v-if="data.clinicalInfo">{{ data.clinicalInfo }}</span>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="金标准分级">
            {{ data.drGradeText || (data.goldDrGrade ? `${data.goldDrGrade} 级` : '—') }}
          </el-descriptions-item>
          <el-descriptions-item label="及格分">
            {{ data.passScore ?? 60 }} 分
          </el-descriptions-item>
          <el-descriptions-item label="金标准诊断" :span="2">
            <span v-if="data.goldDiagnosis">{{ data.goldDiagnosis }}</span>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="教学要点" :span="2">
            <span v-if="data.teachingPoints">{{ data.teachingPoints }}</span>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 缩略图墙 -->
        <div v-if="data.images && data.images.length" class="thumb-wall">
          <div class="thumb-title">影像缩略</div>
          <div class="thumb-grid">
            <div
              v-for="(img, idx) in data.images.slice(0, 6)"
              :key="idx"
              class="thumb-cell"
              @click="onPreview"
            >
              <el-image
                :src="img"
                fit="cover"
                style="width: 100%; height: 100%"
                :preview-src-list="[]"
                :hide-on-click-modal="true"
              >
                <template #error>
                  <div class="thumb-fallback">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
            </div>
            <div
              v-if="data.images.length > 6"
              class="thumb-cell more"
              @click="onPreview"
            >
              + {{ data.images.length - 6 }}
            </div>
          </div>
        </div>
      </template>
      <div v-else-if="!loading" class="empty">
        <el-icon><Picture /></el-icon>
        <span>暂无详情数据</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">关闭</el-button>
      <el-button
        v-if="canEditGold && data"
        type="warning"
        @click="emit('edit-gold', data)"
      >
        {{ data.isPublished ? '修订金标准' : '完善金标准' }}
      </el-button>
      <el-button
        :icon="Picture"
        :disabled="!data || data.imageCount === 0"
        @click="onPreview"
      >
        影像预览
      </el-button>
      <el-button
        v-if="canArchive"
        :type="joinedHere ? 'success' : 'primary'"
        :icon="joinedHere ? Check : Promotion"
        :loading="joiningHere"
        :disabled="joinDisabled"
        @click="onJoin"
      >
        {{ joinButtonText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.case-detail {
  min-height: 200px;
}
.detail-header {
  margin-bottom: 14px;
}
.title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.case-no {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #1677ff;
  font-weight: 700;
  font-size: 16px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}
.meta-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.desc-block {
  margin-bottom: 16px;
}

.thumb-wall {
  margin-top: 12px;
}
.thumb-title {
  font-size: 13px;
  color: #4e5969;
  margin-bottom: 8px;
}
.thumb-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.thumb-cell {
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  background: #f5f6fa;
  border: 1px solid #e5e6eb;
  transition: 0.2s;
  position: relative;
}
.thumb-cell:hover {
  border-color: #1677ff;
  box-shadow: 0 2px 10px rgba(22, 119, 255, 0.18);
}
.thumb-cell.more {
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: #1677ff;
  background: #eef4ff;
}
.thumb-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f6fa;
  color: #c9cdd4;
  font-size: 24px;
}

.muted {
  color: #86909c;
  font-size: 13px;
}

.case-no {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #1677ff;
  font-weight: 600;
}
.case-sn {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #86909c;
  font-size: 12px;
  margin-left: 6px;
}
.phone-text {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #1d2129;
  font-weight: 500;
}

.empty {
  padding: 40px 0;
  text-align: center;
  color: #c9cdd4;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
</style>
