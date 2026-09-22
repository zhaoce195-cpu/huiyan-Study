<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'

import { LearningApi } from '@/api'
import { useUserStore } from '@/stores/user'
import ResourceCard from './components/ResourceCard.vue'
import ResourcePreviewDialog from './components/ResourcePreviewDialog.vue'
import ResourceEditDialog from './components/ResourceEditDialog.vue'
import NoteEditDialog from './components/NoteEditDialog.vue'
import NoteContentView from './components/NoteContentView.vue'

type Resource = LearningApi.LearningResource
type Note = LearningApi.LearningNote
type TabName = 'resources' | 'favorites' | 'notes'

const router = useRouter()
const userStore = useUserStore()

/* ========== 用户与权限 ========== */
const userInfo = computed(() => userStore.userInfo)
const isAdmin = computed(() => userStore.isAdmin)
const canManage = computed(() => userStore.canManage)

const activeTab = ref<TabName>('resources')

/* ========== 资料 ========== */
const resQuery = ref<LearningApi.ResourceListQuery>({
  keyword: '',
  resourceType: '',
  page: 1,
  pageSize: 12
})
const resData = ref<Resource[]>([])
const resTotal = ref(0)
const resLoading = ref(false)

const fetchResources = async () => {
  resLoading.value = true
  try {
    const res = await LearningApi.listResources(resQuery.value)
    resData.value = res.list || []
    resTotal.value = res.total || 0
  } catch {
    resData.value = []
    resTotal.value = 0
  } finally {
    resLoading.value = false
  }
}

const onResPageChange = (p: number) => {
  resQuery.value.page = p
  fetchResources()
}

/* ========== 收藏 ========== */
const favQuery = ref<LearningApi.FavoriteListQuery>({
  keyword: '',
  resourceType: '',
  page: 1,
  pageSize: 12
})
const favData = ref<Resource[]>([])
const favTotal = ref(0)
const favLoading = ref(false)

const fetchFavorites = async () => {
  favLoading.value = true
  try {
    const res = await LearningApi.listFavorites(favQuery.value)
    favData.value = res.list || []
    favTotal.value = res.total || 0
  } catch {
    favData.value = []
    favTotal.value = 0
  } finally {
    favLoading.value = false
  }
}

const onFavPageChange = (p: number) => {
  favQuery.value.page = p
  fetchFavorites()
}

/* ========== 笔记 ========== */
const noteQuery = ref<LearningApi.NoteListQuery>({
  keyword: '',
  page: 1,
  pageSize: 10
})
const noteData = ref<Note[]>([])
const noteTotal = ref(0)
const noteLoading = ref(false)

const fetchNotes = async () => {
  noteLoading.value = true
  try {
    const res = await LearningApi.listNotes(noteQuery.value)
    noteData.value = res.list || []
    noteTotal.value = res.total || 0
  } catch {
    noteData.value = []
    noteTotal.value = 0
  } finally {
    noteLoading.value = false
  }
}

const onNotePageChange = (p: number) => {
  noteQuery.value.page = p
  fetchNotes()
}

/* ========== 收藏切换 ========== */
const updateLocalFav = (r: Resource) => {
  const idx = resData.value.findIndex((x) => x.id === r.id)
  if (idx >= 0) resData.value[idx] = r
  const idx2 = favData.value.findIndex((x) => x.id === r.id)
  if (idx2 >= 0) favData.value[idx2] = r
}

const toggleFavorite = async (r: Resource) => {
  try {
    if (r.isFavorited) {
      await LearningApi.removeFavorite(r.id)
      const next: Resource = {
        ...r,
        isFavorited: false,
        favoriteCount: Math.max(0, r.favoriteCount - 1)
      }
      updateLocalFav(next)
      // 收藏 Tab 中要同步移除
      favData.value = favData.value.filter((x) => x.id !== r.id)
      favTotal.value = Math.max(0, favTotal.value - 1)
    } else {
      const out = await LearningApi.addFavorite({ resourceId: r.id })
      updateLocalFav(out)
    }
  } catch {
    /* error already shown */
  }
}

/* ========== 预览弹窗 ========== */
const previewVisible = ref(false)
const previewResource = ref<Resource | null>(null)
const openPreview = (r: Resource) => {
  previewResource.value = r
  previewVisible.value = true
}
const onPreviewFavChanged = (r: Resource) => {
  previewResource.value = r
  updateLocalFav(r)
}

/* ========== 编辑/上传弹窗 ========== */
const editVisible = ref(false)
const editingResource = ref<Resource | null>(null)
const openCreate = () => {
  if (!canManage.value) {
    ElMessage.warning('仅教师/管理员可上传资料')
    return
  }
  editingResource.value = null
  editVisible.value = true
}
const openEdit = (r: Resource) => {
  editingResource.value = r
  editVisible.value = true
}
const onEditSaved = (_r: Resource) => {
  fetchResources()
}

const removeResource = async (r: Resource) => {
  try {
    await ElMessageBox.confirm(
      `确认删除资料【${r.title}】？该操作不可撤销。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  await LearningApi.deleteResource(r.id)
  fetchResources()
}

/* ========== 笔记弹窗 ========== */
const noteDialogVisible = ref(false)
const editingNote = ref<Note | null>(null)
const noteBind = ref<{
  caseId: number | null
  caseNo: string
  caseTitle: string
  imageIndex: number
  imageUrl: string
  resourceId: number | null
} | null>(null)

const openNoteFromResource = (r: Resource) => {
  editingNote.value = null
  noteBind.value = {
    caseId: r.caseId,
    caseNo: '',
    caseTitle: r.title,
    imageIndex: -1,
    imageUrl: '',
    resourceId: r.id
  }
  noteDialogVisible.value = true
}
const openNewNote = () => {
  editingNote.value = null
  noteBind.value = null
  noteDialogVisible.value = true
}
const editNote = (n: Note) => {
  editingNote.value = n
  noteBind.value = null
  noteDialogVisible.value = true
}
const removeNote = async (n: Note) => {
  try {
    await ElMessageBox.confirm('确认删除该笔记？', '提示', { type: 'warning' })
  } catch {
    return
  }
  await LearningApi.deleteNote(n.id)
  fetchNotes()
}
const onNoteSaved = (_n: Note) => {
  fetchNotes()
}

const goToReadingFromNote = (n: Note) => {
  if (!n.caseId) {
    ElMessage.info('该笔记未绑定病例')
    return
  }
  router.push({ path: '/reading', query: { caseId: String(n.caseId) } })
}

/* ========== 初始化 ========== */
onMounted(() => {
  fetchResources()
})

const onTabChange = (name: string | number) => {
  if (name === 'favorites' && favData.value.length === 0) fetchFavorites()
  if (name === 'notes' && noteData.value.length === 0) fetchNotes()
}


const tagListOf = (s: string) =>
  (s || '').split(',').map((t) => t.trim()).filter(Boolean)
</script>

<template>
  <div class="learning-page">
    <main class="page-body">
      <el-tabs v-model="activeTab" class="learning-tabs" @tab-change="onTabChange">
        <!-- 公共学习资料 -->
        <el-tab-pane name="resources" label="公共学习资料">
          <div class="filter-bar">
            <el-input
              v-model="resQuery.keyword"
              :prefix-icon="Search"
              placeholder="搜索标题 / 简介 / 标签"
              clearable
              style="width: 280px"
              @keyup.enter="(resQuery.page = 1, fetchResources())"
              @clear="(resQuery.page = 1, fetchResources())"
            />
            <el-select
              v-model="resQuery.resourceType"
              placeholder="全部分类"
              clearable
              style="width: 160px"
              @change="(resQuery.page = 1, fetchResources())"
            >
              <el-option
                v-for="o in LearningApi.RESOURCE_TYPE_OPTIONS"
                :key="o.value"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
            <el-button type="primary" @click="(resQuery.page = 1, fetchResources())">
              查询
            </el-button>
            <div class="spacer" />
            <el-button
              v-if="canManage"
              type="primary"
              :icon="Plus"
              @click="openCreate"
            >
              上传资料
            </el-button>
          </div>

          <div v-loading="resLoading" class="card-grid">
            <ResourceCard
              v-for="r in resData"
              :key="r.id"
              :resource="r"
              :can-edit="canManage && (isAdmin || r.publisherId === userInfo.id)"
              :can-delete="canManage && (isAdmin || r.publisherId === userInfo.id)"
              @preview="openPreview"
              @toggle-fav="toggleFavorite"
              @edit="openEdit"
              @delete="removeResource"
              @note="openNoteFromResource"
            />
          </div>

          <el-empty v-if="!resLoading && resData.length === 0" description="暂无资料" />

          <el-pagination
            v-if="resTotal > 0"
            :current-page="resQuery.page"
            :page-size="resQuery.pageSize"
            :total="resTotal"
            layout="total, prev, pager, next, jumper"
            class="pager"
            @current-change="onResPageChange"
          />
        </el-tab-pane>

        <!-- 我的收藏 -->
        <el-tab-pane name="favorites" label="我的收藏">
          <div class="filter-bar">
            <el-input
              v-model="favQuery.keyword"
              :prefix-icon="Search"
              placeholder="搜索"
              clearable
              style="width: 280px"
              @keyup.enter="(favQuery.page = 1, fetchFavorites())"
              @clear="(favQuery.page = 1, fetchFavorites())"
            />
            <el-select
              v-model="favQuery.resourceType"
              placeholder="全部分类"
              clearable
              style="width: 160px"
              @change="(favQuery.page = 1, fetchFavorites())"
            >
              <el-option
                v-for="o in LearningApi.RESOURCE_TYPE_OPTIONS"
                :key="o.value"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
            <el-button type="primary" @click="(favQuery.page = 1, fetchFavorites())">
              查询
            </el-button>
          </div>

          <div v-loading="favLoading" class="card-grid">
            <ResourceCard
              v-for="r in favData"
              :key="r.id"
              :resource="r"
              :can-edit="false"
              :can-delete="false"
              @preview="openPreview"
              @toggle-fav="toggleFavorite"
              @note="openNoteFromResource"
            />
          </div>

          <el-empty
            v-if="!favLoading && favData.length === 0"
            description="还没有收藏，先去公共资料里挑几份吧"
          />

          <el-pagination
            v-if="favTotal > 0"
            :current-page="favQuery.page"
            :page-size="favQuery.pageSize"
            :total="favTotal"
            layout="total, prev, pager, next, jumper"
            class="pager"
            @current-change="onFavPageChange"
          />
        </el-tab-pane>

        <!-- 我的笔记 -->
        <el-tab-pane name="notes" label="我的笔记">
          <div class="filter-bar">
            <el-input
              v-model="noteQuery.keyword"
              :prefix-icon="Search"
              placeholder="搜索标题 / 内容 / 标签"
              clearable
              style="width: 280px"
              @keyup.enter="(noteQuery.page = 1, fetchNotes())"
              @clear="(noteQuery.page = 1, fetchNotes())"
            />
            <el-button type="primary" @click="(noteQuery.page = 1, fetchNotes())">
              查询
            </el-button>
            <div class="spacer" />
            <el-button type="primary" :icon="Plus" @click="openNewNote">
              新建笔记
            </el-button>
          </div>

          <div v-loading="noteLoading" class="note-list">
            <div v-for="n in noteData" :key="n.id" class="note-item">
              <div class="note-head">
                <h3 class="note-title">{{ n.title || '（未命名笔记）' }}</h3>
                <span class="note-time">{{ n.updatedAt || n.createdAt }}</span>
              </div>
              <div v-if="n.caseId" class="bind-line">
                绑定病例
                <el-link type="primary" @click="goToReadingFromNote(n)">
                  {{ n.caseNo || `#${n.caseId}` }}
                  <span v-if="n.caseTitle"> · {{ n.caseTitle }}</span>
                </el-link>
                <span v-if="n.imageIndex >= 0"> · 影像 #{{ n.imageIndex + 1 }}</span>
              </div>
              <NoteContentView class="note-content" :content="n.content" />
              <div v-if="tagListOf(n.tags).length" class="note-tags">
                <el-tag
                  v-for="t in tagListOf(n.tags)"
                  :key="t"
                  size="small"
                  effect="plain"
                >
                  {{ t }}
                </el-tag>
              </div>
              <div class="note-actions">
                <el-button size="small" type="primary" plain @click="editNote(n)">
                  编辑
                </el-button>
                <el-button
                  v-if="n.caseId"
                  size="small"
                  plain
                  @click="goToReadingFromNote(n)"
                >
                  打开阅片复盘
                </el-button>
                <el-button size="small" type="danger" plain @click="removeNote(n)">
                  删除
                </el-button>
              </div>
            </div>
          </div>

          <el-empty
            v-if="!noteLoading && noteData.length === 0"
            description="还没有笔记，写下第一条临床思考吧"
          />

          <el-pagination
            v-if="noteTotal > 0"
            :current-page="noteQuery.page"
            :page-size="noteQuery.pageSize"
            :total="noteTotal"
            layout="total, prev, pager, next, jumper"
            class="pager"
            @current-change="onNotePageChange"
          />
        </el-tab-pane>
      </el-tabs>
    </main>

    <!-- 弹窗 -->
    <ResourcePreviewDialog
      v-model:visible="previewVisible"
      :resource="previewResource"
      @fav-changed="onPreviewFavChanged"
      @note="openNoteFromResource"
    />
    <ResourceEditDialog
      v-model:visible="editVisible"
      :resource="editingResource"
      @saved="onEditSaved"
    />
    <NoteEditDialog
      v-model:visible="noteDialogVisible"
      :note="editingNote"
      :bind="noteBind"
      @saved="onNoteSaved"
    />
  </div>
</template>

<style scoped>
.learning-page {
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
.page-header .title {
  margin-left: 12px;
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
.learning-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
}
.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  align-items: center;
}
.spacer {
  flex: 1;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
  min-height: 200px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.note-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}
.note-item {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 14px 18px;
}
.note-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.note-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}
.note-time {
  color: #c9cdd4;
  font-size: 12px;
}
.bind-line {
  font-size: 12px;
  color: #4e5969;
  margin-bottom: 6px;
}
.note-content {
  margin: 6px 0;
  white-space: pre-wrap;
  color: #4e5969;
  line-height: 1.7;
  font-size: 13px;
}
.note-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}
.note-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}
</style>
