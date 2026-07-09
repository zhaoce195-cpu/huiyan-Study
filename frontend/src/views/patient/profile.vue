<script setup lang="ts">
/**
 * PATIENT 端 · 个人中心
 * - 基本信息卡片：头像 / 昵称 / 手机号 / 角色 / 当前机构 / 注册时间
 * - 操作：上传头像 / 修改昵称 / 修改密码 / 退出登录
 * - 申请加入机构：嵌入卡片（OrgApplyDialog） + 我的申请历史
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Lock, SwitchButton, UploadFilled } from '@element-plus/icons-vue'
import { LoginApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { useLogout } from '@/composables/useLogout'

const userStore = useUserStore()
const { logout } = useLogout()

const userInfo = computed(() => userStore.userInfo)
const displayName = computed(() => userStore.displayName)
const phone = computed(() => userInfo.value.phone || userInfo.value.username || '—')
const organization = computed(() => userInfo.value.department || '')
const registeredAt = computed(() => (userInfo.value as any).createdAt || (userInfo.value as any).lastLoginAt || '')

/* ========== 修改昵称 ========== */
const editName = async () => {
  let next = ''
  try {
    const r = await ElMessageBox.prompt('请输入新的昵称', '修改昵称', {
      inputValue: displayName.value === '医师' ? '' : displayName.value,
      inputPlaceholder: '昵称（1-32 字）',
      inputValidator: (v: string) => {
        const t = (v || '').trim()
        if (!t) return '昵称不能为空'
        if (t.length > 32) return '昵称不超过 32 字'
        return true
      },
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    next = (r.value || '').trim()
  } catch {
    return
  }
  try {
    const u = await LoginApi.updateProfile({ realName: next })
    if (u) {
      userStore.setUser(u)
      ElMessage.success('昵称已更新')
    }
  } catch {
    /* 已弹错误 */
  }
}

/* ========== 修改密码 ========== */
const passwordVisible = ref(false)
const passwordForm = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const submittingPwd = ref(false)
const onChangePassword = async () => {
  const { oldPassword, newPassword, confirm } = passwordForm
  if (!oldPassword || !newPassword) {
    ElMessage.warning('请填写完整')
    return
  }
  if (newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (newPassword !== confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  submittingPwd.value = true
  try {
    await LoginApi.changePassword({ oldPassword, newPassword })
    ElMessage.success('密码已修改，下次登录请使用新密码')
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirm = ''
    passwordVisible.value = false
  } catch {
    /* 已弹错误 */
  } finally {
    submittingPwd.value = false
  }
}

/* ========== 上传头像（复用 LoginApi.uploadAvatar） ========== */
const uploading = ref(false)
const onAvatarChange = async (file: File) => {
  if (!file) return
  if (!/\.(jpg|jpeg|png|webp)$/i.test(file.name)) {
    ElMessage.warning('仅支持 JPG / PNG / WEBP')
    return
  }
  if (file.size / 1024 / 1024 > 5) {
    ElMessage.warning('头像不超过 5MB')
    return
  }
  uploading.value = true
  try {
    const r = await LoginApi.uploadAvatar(file)
    if (r?.avatarUrl) {
      userStore.setUser({ ...(userStore.userInfo as any), avatar: r.avatarUrl })
      ElMessage.success('头像已更新')
    }
  } catch {
    /* 已弹错误 */
  } finally {
    uploading.value = false
  }
}
const onAvatarPick = (rawFile: any) => {
  const f: File | undefined = rawFile?.raw || rawFile
  if (f instanceof File) onAvatarChange(f)
  return false
}

/* ========== 退出登录 ========== */
// 已迁移到 composables/useLogout

onMounted(async () => {
  try { await userStore.fetchProfile() } catch { /* ignore */ }
})
</script>

<template>
  <div class="patient-profile">
    <header class="page-head">
      <h2>个人中心</h2>
      <div class="muted">查看与维护账户基本信息 · 申请加入机构 · 修改密码</div>
    </header>

    <div class="grid">
      <!-- 基本信息卡片 -->
      <section class="card">
        <div class="card-title">基本信息</div>
        <div class="info-row">
          <el-upload
            class="avatar-upload"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="onAvatarPick"
            accept=".jpg,.jpeg,.png,.webp"
          >
            <el-avatar
              :size="80"
              :src="userInfo.avatar"
              style="background:#eef4ff;color:#1677ff;font-size:28px;cursor:pointer"
            >
              {{ displayName.charAt(0) }}
            </el-avatar>
            <div class="avatar-tip">
              <el-icon><UploadFilled /></el-icon>
              <span>{{ uploading ? '上传中…' : '点击更换头像' }}</span>
            </div>
          </el-upload>

          <div class="info-grid">
            <div class="cell">
              <span class="lbl">昵称</span>
              <span class="val">{{ displayName }}</span>
              <el-button text type="primary" :icon="Edit" size="small" @click="editName">
                修改
              </el-button>
            </div>
            <div class="cell">
              <span class="lbl">手机号</span>
              <span class="val mono">{{ phone }}</span>
            </div>
            <div class="cell">
              <span class="lbl">当前机构</span>
              <span v-if="organization" class="val">{{ organization }}</span>
              <span v-else class="val muted">尚未加入任何机构</span>
            </div>
            <div class="cell" v-if="registeredAt">
              <span class="lbl">注册时间</span>
              <span class="val">{{ registeredAt }}</span>
            </div>
          </div>
        </div>

        <div class="card-actions">
          <el-button :icon="Lock" @click="passwordVisible = true">修改密码</el-button>
          <el-button :icon="SwitchButton" type="danger" plain @click="logout">退出登录</el-button>
        </div>
      </section>
    </div>

    <!-- 修改密码 -->
    <el-dialog v-model="passwordVisible" title="修改密码" width="420">
      <el-form label-width="84px">
        <el-form-item label="当前密码">
          <el-input v-model="passwordForm.oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.newPassword" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="passwordForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingPwd" @click="onChangePassword">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.patient-profile {
  max-width: 1100px;
  margin: 0 auto;
  padding: 28px 32px 40px;
}
.page-head { margin-bottom: 18px; }
.page-head h2 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #1d2129; }
.page-head .muted { color: #86909c; font-size: 13px; }

.grid { display: grid; grid-template-columns: 1fr; gap: 16px; }

.card {
  background: #fff;
  border: 1px solid #e6effe;
  border-radius: 14px;
  padding: 20px 22px;
}
.card-title {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 700;
  color: #1d2129;
  margin-bottom: 14px;
}

.info-row {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.avatar-upload {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.avatar-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #1677ff;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}

.info-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}
.cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #1d2129;
}
.cell .lbl { width: 70px; flex-shrink: 0; color: #86909c; font-size: 12px; }
.cell .val { color: #1d2129; }
.cell .val.muted { color: #c9cdd4; }
.cell .val.mono { font-family: 'Consolas', 'Monaco', monospace; color: #1677ff; }

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed #eef4ff;
}

.empty {
  padding: 24px 0;
  color: #86909c;
  text-align: center;
  font-size: 13px;
  line-height: 1.7;
}

.app-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.app-item {
  background: #fafbfc;
  border: 1px solid #eef4ff;
  border-radius: 10px;
  padding: 12px 14px;
}
.app-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.app-line .org { font-weight: 600; color: #1d2129; }
.app-line .time { margin-left: auto; }
.app-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #4e5969;
}
.app-sub .lbl { color: #86909c; margin-right: 4px; }
.multiline { white-space: pre-wrap; word-break: break-word; }
.muted { color: #86909c; }
.muted.small { font-size: 11px; }

@media (max-width: 720px) {
  .info-row { flex-direction: column; align-items: stretch; }
  .info-grid { grid-template-columns: 1fr; }
}
</style>
