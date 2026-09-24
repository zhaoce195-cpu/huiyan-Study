<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Search, Key, User } from '@element-plus/icons-vue'
import { AdminUsersApi, CommonApi } from '@/api'
import { useUserStore } from '@/stores/user'

type Item = AdminUsersApi.AdminUserItem
type Role = AdminUsersApi.AdminRole

const props = defineProps<{
  canManage: boolean
}>()

const userStore = useUserStore()
const myId = computed(() => Number(userStore.userInfo.id))

const ROLE_OPTIONS: { label: string; value: Role }[] = [
  { label: '学员', value: 'STUDENT' },
  { label: '带教教师', value: 'TEACHER' },
  { label: '管理员', value: 'ADMIN' }
]

const roleText = (code: string) =>
  ROLE_OPTIONS.find((o) => o.value === code)?.label || code

const roleTag = (code: string) => {
  if (code === 'ADMIN') return 'danger'
  if (code === 'TEACHER') return 'warning'
  return 'primary'
}

/* ========== 列表 ========== */

const list = ref<Item[]>([])
const loading = ref(false)
const filter = reactive({
  keyword: '',
  role: '' as Role | '',
  isActive: '' as boolean | ''
})
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const fetchList = async () => {
  if (!props.canManage) return
  loading.value = true
  try {
    const res = await AdminUsersApi.getAdminUserList({
      keyword: filter.keyword,
      role: filter.role,
      isActive: filter.isActive,
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

const onSearch = () => {
  pagination.page = 1
  fetchList()
}

const onReset = () => {
  filter.keyword = ''
  filter.role = ''
  filter.isActive = ''
  pagination.page = 1
  fetchList()
}

/* ========== 新建 ========== */

const depts = ref<CommonApi.Department[]>([])
const fetchDepts = async () => {
  try {
    depts.value = ((await CommonApi.getDepartmentList()) || []).filter(
      (row) => row.hospitalId != null
    )
  } catch {
    depts.value = []
  }
}

const createVisible = ref(false)
const createLoading = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive<AdminUsersApi.AdminUserCreate & { departmentPick: number | string }>({
  username: '',
  realName: '',
  role: 'STUDENT',
  department: '',
  departmentPick: '',
  password: ''
})

const createRules: FormRules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    { min: 2, max: 32, message: '账号长度 2~32 位', trigger: 'blur' }
  ],
  realName: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [
    { required: true, message: '请设置初始密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
    {
      validator: (_r, v: string, cb) => {
        if (v && (/^\d+$/.test(v) || /^[A-Za-z]+$/.test(v))) {
          cb(new Error('密码需包含字母与数字'))
        } else cb()
      },
      trigger: 'blur'
    }
  ]
}

const deptLabel = (row: CommonApi.Department) =>
  row.hospitalName ? `${row.name} · ${row.hospitalName}` : row.name

const openCreate = () => {
  createForm.username = ''
  createForm.realName = ''
  createForm.role = 'STUDENT'
  createForm.department = ''
  createForm.departmentPick = ''
  createForm.password = ''
  createVisible.value = true
}

const submitCreate = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    createLoading.value = true
    try {
      const chosen = depts.value.find((row) => Number(row.id) === Number(createForm.departmentPick))
      await AdminUsersApi.createAdminUser({
        username: createForm.username,
        realName: createForm.realName,
        role: createForm.role,
        department: chosen ? chosen.name : String(createForm.departmentPick || ''),
        departmentId: chosen && chosen.hospitalId != null ? Number(chosen.id) : undefined,
        password: createForm.password
      })
      createVisible.value = false
      fetchList()
    } catch {
      /* 拦截器已弹错 */
    } finally {
      createLoading.value = false
    }
  })
}

/* ========== 重置密码 ========== */

const resetPwd = async (row: Item) => {
  try {
    await ElMessageBox.confirm(
      `将为「${row.realName || row.username}」生成临时密码，原密码立即失效，对方下次登录必须改密。`,
      '重置密码',
      { type: 'warning', confirmButtonText: '生成临时密码', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const res = await AdminUsersApi.resetAdminUserPassword(row.id)
    row.mustChangePassword = true
    await ElMessageBox.alert(
      `账号 ${res.username} 的临时密码：\n\n${res.tempPassword}\n\n请立即告知本人，登录后必须修改。`,
      '临时密码（只显示一次）',
      { confirmButtonText: '我已抄录', type: 'success' }
    )
  } catch {
    /* 取消或失败 */
  }
}

/* ========== 停用 / 启用 ========== */

const toggleActive = async (row: Item) => {
  const next = !row.isActive
  const verb = next ? '启用' : '停用'
  if (!next && row.id === myId.value) {
    ElMessage.warning('不能停用当前登录账号')
    return
  }
  try {
    await ElMessageBox.confirm(
      next
        ? `确定启用账号「${row.realName || row.username}」？启用后可正常登录。`
        : `确定停用账号「${row.realName || row.username}」？停用后将无法登录。`,
      `${verb}确认`,
      { type: next ? 'info' : 'warning', confirmButtonText: `确定${verb}`, cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const updated = await AdminUsersApi.setAdminUserActive(row.id, next)
    row.isActive = updated.isActive
  } catch {
    /* 拦截器已弹错 */
  }
}

onMounted(() => {
  fetchList()
  fetchDepts()
})
</script>

<template>
  <div class="users-section">
    <div v-if="!canManage" class="card">
      <el-alert
        title="当前账号无用户管理权限"
        type="warning"
        description="仅平台管理员可新建、重置密码或停用账号。"
        :closable="false"
        show-icon
      />
    </div>

    <div v-else class="card">
      <div class="toolbar">
        <el-input
          v-model="filter.keyword"
          placeholder="姓名 / 账号 / 科室"
          clearable
          style="width: 220px"
          :prefix-icon="Search"
          @keyup.enter="onSearch"
        />
        <el-select v-model="filter.role" placeholder="角色" clearable style="width: 140px">
          <el-option v-for="o in ROLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filter.isActive" placeholder="状态" clearable style="width: 120px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
        <el-button :icon="Refresh" @click="onReset">清除</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建账号</el-button>
      </div>

      <el-table v-loading="loading" :data="list" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column prop="realName" label="姓名" width="140">
          <template #default="{ row }">{{ row.realName || '—' }}</template>
        </el-table-column>
        <el-table-column prop="username" label="账号" width="160" />
        <el-table-column label="角色" width="140">
          <template #default="{ row }">
            <el-tag size="small" :type="roleTag(row.role)" effect="plain">
              {{ row.roleName || roleText(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="科室" min-width="220">
          <template #default="{ row }">
            <span v-if="row.department">
              {{ row.department }}
              <span v-if="row.hospitalName" class="muted"> · {{ row.hospitalName }}</span>
            </span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="100">
          <template #default="{ row }">
            <el-tag :type="row.isActive ? 'success' : 'info'" size="small">
              {{ row.isActive ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="改密" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.mustChangePassword" type="warning" size="small" effect="plain">
              下次必改
            </el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" :icon="Key" @click="resetPwd(row)">
              重置密码
            </el-button>
            <el-button
              text
              size="small"
              :type="row.isActive ? 'danger' : 'success'"
              :disabled="row.isActive && row.id === myId"
              @click="toggleActive(row)"
            >
              {{ row.isActive ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="pagination.total > 0" class="pager">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          background
          layout="total, sizes, prev, pager, next"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </div>

    <el-dialog
      v-model="createVisible"
      title="新建账号"
      width="480"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="88px">
        <el-form-item label="姓名" prop="realName">
          <el-input v-model="createForm.realName" maxlength="32" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="账号" prop="username">
          <el-input v-model="createForm.username" maxlength="32" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-radio-group v-model="createForm.role">
            <el-radio-button v-for="o in ROLE_OPTIONS" :key="o.value" :value="o.value">
              {{ o.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="科室">
          <el-select
            v-model="createForm.departmentPick"
            filterable
            allow-create
            clearable
            placeholder="选择医院下的科室"
            style="width: 100%"
          >
            <el-option
              v-for="d in depts"
              :key="d.id"
              :label="deptLabel(d)"
              :value="Number(d.id)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="初密" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            maxlength="64"
            placeholder="至少 6 位，须含字母和数字"
          />
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="初始密码由管理员设定。对方首次登录后须改密，才能继续使用系统。"
      />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :icon="User" :loading="createLoading" @click="submitCreate">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 16px 18px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
.muted {
  color: #86909c;
}
</style>
