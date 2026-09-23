<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { CommonApi } from '@/api'

type OperationLog = CommonApi.OperationLog

const props = defineProps<{
  /** 是否具有日志查询权限（仅 ADMIN） */
  canManage: boolean
}>()

const list = ref<OperationLog[]>([])
const loading = ref(false)
const filter = reactive({
  module: '' as string | '',
  range: [] as string[]
})
const pagination = reactive({ page: 1, pageSize: 50, total: 0 })

const MODULES = [
  { code: 'common', label: '公共' },
  { code: 'auth', label: '登录鉴权' },
  { code: 'training', label: '培训' },
  { code: 'screening', label: '筛查' },
  { code: 'user', label: '用户中心' }
]

const fetchList = async () => {
  if (!props.canManage) return
  loading.value = true
  try {
    const res = await CommonApi.getOperationLogs({
      module: filter.module || undefined,
      startTime: filter.range?.[0] || undefined,
      endTime: filter.range?.[1] || undefined,
      page: pagination.page,
      pageSize: pagination.pageSize
    })
    list.value = res?.list || []
    pagination.total = res?.total || 0
  } catch {
    list.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const onFilter = () => {
  pagination.page = 1
  fetchList()
}

const clearFilters = () => {
  filter.module = ''
  filter.range = []
  onFilter()
}

const moduleLabel = (code: string) =>
  MODULES.find((m) => m.code === code)?.label || code

const actionTagType = (action: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (/create|register|publish/i.test(action)) return 'success'
  if (/update|edit|reanalyze/i.test(action)) return 'warning'
  if (/delete|remove|logout/i.test(action)) return 'danger'
  return 'info'
}

onMounted(fetchList)
</script>

<template>
  <div class="logs-section">
    <div v-if="!canManage" class="card">
      <el-alert
        title="当前账号无系统日志查询权限"
        type="warning"
        description="仅平台管理员（ADMIN）可查看操作日志，请联系系统管理员。"
        :closable="false"
        show-icon
      />
    </div>

    <div v-else class="card">
      <div class="card-header">
        <div class="card-title">
          操作日志
          <span class="muted ml8">共 {{ pagination.total }} 条</span>
        </div>
        <div class="card-actions">
          <el-select
            v-model="filter.module"
            placeholder="模块"
            clearable
            size="small"
            style="width: 140px"
            @change="onFilter"
          >
            <el-option
              v-for="m in MODULES"
              :key="m.code"
              :label="m.label"
              :value="m.code"
            />
          </el-select>
          <el-date-picker
            v-model="filter.range"
            type="datetimerange"
            value-format="YYYY-MM-DD HH:mm:ss"
            range-separator="—"
            start-placeholder="起始时间"
            end-placeholder="结束时间"
            size="small"
            style="width: 360px"
            @change="onFilter"
          />
          <el-button size="small" @click="clearFilters">清除</el-button>
          <el-button :icon="Search" size="small" type="primary" @click="onFilter">查询</el-button>
          <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column prop="id" label="日志ID" width="80" />
        <el-table-column label="模块" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ moduleLabel(row.module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small" effect="dark">
              {{ row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="操作人" width="120">
          <template #default="{ row }">
            {{ row.username || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="140">
          <template #default="{ row }">
            <span v-if="row.ip" class="mono">{{ row.ip }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="280" show-overflow-tooltip />
        <el-table-column prop="createdAt" label="时间" width="170" />
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '暂无日志' }}</div>
        </template>
      </el-table>

      <div v-if="pagination.total > pagination.pageSize" class="pagination">
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
    </div>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 18px 20px;
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
  flex-wrap: wrap;
}
.muted {
  color: #86909c;
  font-size: 12px;
  font-weight: 400;
}
.ml8 {
  margin-left: 8px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
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
</style>
