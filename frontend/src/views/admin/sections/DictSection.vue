<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { CommonApi } from '@/api'

type DictItem = CommonApi.DictItem

const DICT_TYPES: { code: string; label: string }[] = [
  { code: 'dr_level', label: 'DR 分级' },
  { code: 'lesion_type', label: '病变类型' },
  { code: 'risk_level', label: '风险等级' },
  { code: 'eye_side', label: '眼别' },
  { code: 'gender', label: '性别' },
  { code: 'difficulty', label: '难度' },
  { code: 'annotation_type', label: '标注类型' },
  { code: 'case_category', label: '病例分类' },
  { code: 'role', label: '角色' },
  { code: 'notice_type', label: '公告类型' }
]

const dictMap = ref<Record<string, DictItem[]>>({})
const loading = ref(false)
const activeType = ref<string>(DICT_TYPES[0].code)

const fetchAll = async () => {
  loading.value = true
  try {
    const codes = DICT_TYPES.map((t) => t.code)
    const res = await CommonApi.getDictBatch(codes)
    dictMap.value = res || {}
  } catch {
    dictMap.value = {}
  } finally {
    loading.value = false
  }
}

const fetchOne = async (code: string) => {
  loading.value = true
  try {
    const res = await CommonApi.getDict(code)
    dictMap.value = { ...dictMap.value, [code]: res || [] }
    ElMessage.success(`已刷新字典 ${code}`)
  } catch {
    /* 已弹错误提示 */
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)
</script>

<template>
  <div class="dict-section">
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          字典数据
          <span class="muted ml8">共 {{ DICT_TYPES.length }} 类</span>
        </div>
        <div class="card-actions">
          <el-button :icon="Refresh" size="small" @click="fetchAll">全部刷新</el-button>
        </div>
      </div>

      <el-tabs v-model="activeType" type="border-card" v-loading="loading">
        <el-tab-pane
          v-for="t in DICT_TYPES"
          :key="t.code"
          :label="t.label"
          :name="t.code"
        >
          <div class="tab-toolbar">
            <span class="dict-code">{{ t.code }}</span>
            <span class="muted">共 {{ (dictMap[t.code] || []).length }} 项</span>
            <el-button text type="primary" size="small" :icon="Refresh" @click="fetchOne(t.code)">
              刷新本字典
            </el-button>
          </div>
          <el-table :data="dictMap[t.code] || []" size="small" stripe border>
            <el-table-column type="index" label="#" width="56" />
            <el-table-column prop="code" label="编码" width="160">
              <template #default="{ row }">
                <code class="code-tag">{{ row.code }}</code>
              </template>
            </el-table-column>
            <el-table-column prop="label" label="显示名称" min-width="200" />
            <el-table-column prop="sort" label="排序" width="80" />
            <el-table-column prop="remark" label="备注" min-width="200">
              <template #default="{ row }">
                <span v-if="row.remark">{{ row.remark }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <template #empty>
              <div class="empty">暂无数据</div>
            </template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
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
.muted {
  color: #86909c;
  font-size: 12px;
  font-weight: 400;
}
.ml8 {
  margin-left: 8px;
}
.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.dict-code {
  background: #f2f3f5;
  color: #1677ff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}
.code-tag {
  background: #f7faff;
  border: 1px solid #e0eafc;
  color: #1677ff;
  padding: 1px 8px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}
.empty {
  padding: 36px 0;
  text-align: center;
  color: #c9cdd4;
  font-size: 14px;
}
</style>
