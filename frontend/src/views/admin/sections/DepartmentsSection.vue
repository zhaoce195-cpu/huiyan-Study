<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Search, Edit, Delete, OfficeBuilding } from '@element-plus/icons-vue'
import { CommonApi } from '@/api'

type Department = CommonApi.Department
type Hospital = CommonApi.Hospital

const props = defineProps<{
  /** 是否具有写权限（仅 ADMIN） */
  canManage: boolean
}>()

/* ========== 医院列表 ========== */

const hospitals = ref<Hospital[]>([])
const hospitalKeyword = ref('')
const hospitalLoading = ref(false)

const fetchHospitals = async () => {
  hospitalLoading.value = true
  try {
    const res = await CommonApi.getHospitalList(hospitalKeyword.value || undefined)
    hospitals.value = res || []
  } catch {
    hospitals.value = []
  } finally {
    hospitalLoading.value = false
  }
}

/* ========== 科室列表 ========== */

const selectedHospitalId = ref<number | string | ''>('')
const depts = ref<Department[]>([])
const deptLoading = ref(false)

const fetchDepts = async () => {
  deptLoading.value = true
  try {
    const res = await CommonApi.getDepartmentList(selectedHospitalId.value || undefined)
    depts.value = res || []
  } catch {
    depts.value = []
  } finally {
    deptLoading.value = false
  }
}

const onHospitalChange = () => {
  fetchDepts()
}

/** 列表里直接显示医院名，光给一个 ID 没人认得出是哪家 */
const hospitalName = (id: number | string): string =>
  hospitals.value.find((h) => String(h.id) === String(id))?.name || `医院 #${id}`

/* ========== 新建 / 编辑 ========== */

const editVisible = ref(false)
const editLoading = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive<CommonApi.DepartmentSaveParams & { id?: number | string }>({
  id: undefined,
  // 留空 = 全院通用科室，所有医院都能看到
  hospitalId: undefined,
  code: '',
  name: '',
  shortName: '',
  leader: '',
  phone: '',
  sortOrder: 0,
  isActive: true,
  remark: ''
})
const editRules: FormRules = {
  name: [{ required: true, message: '请输入科室名称', trigger: 'blur' }]
}
const isEditing = () => editForm.id != null

const openCreate = () => {
  editForm.id = undefined
  // 顺手带上左侧正在筛选的医院，避免建完发现归错了地方
  editForm.hospitalId = (selectedHospitalId.value as number) || undefined
  editForm.code = ''
  editForm.name = ''
  editForm.shortName = ''
  editForm.leader = ''
  editForm.phone = ''
  editForm.sortOrder = 0
  editForm.isActive = true
  editForm.remark = ''
  editVisible.value = true
}
const openEdit = (d: Department) => {
  editForm.id = d.id
  editForm.hospitalId = (d.hospitalId as number) ?? undefined
  editForm.code = ''
  editForm.name = d.name
  editForm.shortName = ''
  editForm.leader = ''
  editForm.phone = ''
  editForm.sortOrder = 0
  editForm.isActive = true
  editForm.remark = ''
  editVisible.value = true
}

const submitEdit = async () => {
  if (!editFormRef.value) return
  await editFormRef.value.validate(async (valid) => {
    if (!valid) return
    editLoading.value = true
    try {
      const payload: CommonApi.DepartmentSaveParams = {
        hospitalId: editForm.hospitalId ?? undefined,
        code: editForm.code || undefined,
        name: editForm.name,
        shortName: editForm.shortName || undefined,
        leader: editForm.leader || undefined,
        phone: editForm.phone || undefined,
        sortOrder: editForm.sortOrder ?? 0,
        isActive: editForm.isActive ?? true,
        remark: editForm.remark || undefined
      }
      if (editForm.id != null) {
        await CommonApi.updateDepartment(editForm.id, payload)
      } else {
        await CommonApi.createDepartment(payload)
      }
      editVisible.value = false
      fetchDepts()
    } catch {
      /* 已弹错误提示 */
    } finally {
      editLoading.value = false
    }
  })
}

const removeDept = async (d: Department) => {
  try {
    await ElMessageBox.confirm(`确定删除科室「${d.name}」？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await CommonApi.deleteDepartment(d.id)
    fetchDepts()
  } catch {
    /* 已弹错误提示 */
  }
}

onMounted(() => {
  fetchHospitals()
  fetchDepts()
})
</script>

<template>
  <div class="dept-section">
    <!-- 医院列表 -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <el-icon><OfficeBuilding /></el-icon>
          医院列表
          <span class="muted ml8">共 {{ hospitals.length }} 家</span>
        </div>
        <div class="card-actions">
          <el-input
            v-model="hospitalKeyword"
            placeholder="搜索医院名称"
            :prefix-icon="Search"
            clearable
            size="small"
            style="width: 220px"
            @change="fetchHospitals"
            @clear="fetchHospitals"
          />
          <el-button :icon="Refresh" size="small" @click="fetchHospitals">刷新</el-button>
        </div>
      </div>
      <el-table v-loading="hospitalLoading" :data="hospitals" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="医院名称" min-width="240" />
        <el-table-column prop="level" label="等级" width="120">
          <template #default="{ row }">
            <span v-if="row.level">{{ row.level }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="province" label="省份" width="120" />
        <el-table-column prop="city" label="城市" width="120" />
        <template #empty>
          <div class="empty">暂无医院数据</div>
        </template>
      </el-table>
    </div>

    <!-- 科室列表 -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          科室管理
          <span class="muted ml8">共 {{ depts.length }} 个</span>
        </div>
        <div class="card-actions">
          <el-select
            v-model="selectedHospitalId"
            placeholder="按医院筛选（留空 = 全部）"
            clearable
            filterable
            size="small"
            style="width: 240px"
            @change="onHospitalChange"
            @clear="onHospitalChange"
          >
            <el-option
              v-for="h in hospitals"
              :key="h.id"
              :label="h.name"
              :value="h.id"
            />
          </el-select>
          <el-button :icon="Refresh" size="small" @click="fetchDepts">刷新</el-button>
          <el-button
            v-if="canManage"
            :icon="Plus"
            size="small"
            type="primary"
            @click="openCreate"
          >
            新建科室
          </el-button>
        </div>
      </div>
      <el-table v-loading="deptLoading" :data="depts" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="科室名称" min-width="240" />
        <el-table-column prop="hospitalId" label="所属医院" min-width="180">
          <template #default="{ row }">
            <span v-if="row.hospitalId != null">{{ hospitalName(row.hospitalId) }}</span>
            <el-tag v-else size="small" effect="plain">全院通用</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="canManage" label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button text type="warning" size="small" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" :icon="Delete" @click="removeDept(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ deptLoading ? '加载中…' : '暂无科室数据' }}</div>
        </template>
      </el-table>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="editVisible"
      :title="isEditing() ? '编辑科室' : '新建科室'"
      width="540"
      :close-on-click-modal="false"
    >
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="100px">
        <el-form-item label="所属医院">
          <el-select
            v-model="editForm.hospitalId"
            placeholder="留空 = 全院通用"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="h in hospitals"
              :key="String(h.id)"
              :label="h.name"
              :value="h.id"
            />
          </el-select>
          <div class="form-hint">
            选定医院后，该科室只在这家医院下可见；留空则所有医院通用。
          </div>
        </el-form-item>
        <el-form-item label="科室编码">
          <el-input v-model="editForm.code" maxlength="32" placeholder="可留空" />
          <div class="form-hint">同一医院内不可重复，不同医院可以重名。</div>
        </el-form-item>
        <el-form-item label="科室名称" prop="name">
          <el-input v-model="editForm.name" maxlength="64" />
        </el-form-item>
        <el-form-item label="简称">
          <el-input v-model="editForm.shortName" maxlength="32" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="editForm.leader" maxlength="32" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="editForm.phone" maxlength="32" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="editForm.sortOrder" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.isActive" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
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
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}
.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.form-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.6;
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
</style>
