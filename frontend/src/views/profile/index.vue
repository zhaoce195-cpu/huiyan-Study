<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadRequestOptions
} from 'element-plus'
import { Lock, User, Setting, Picture, Camera } from '@element-plus/icons-vue'
import { LoginApi } from '@/api'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

/* ========== 当前用户信息 ========== */

const userInfo = computed<Partial<LoginApi.UserInfo>>(() => userStore.userInfo)
const userLoading = ref(false)

const displayName = computed(() => userStore.displayName)
const avatarLetter = computed(() => displayName.value.charAt(0).toUpperCase())
const roleName = computed(() => userStore.roleName)

const fetchProfile = async () => {
  userLoading.value = true
  try {
    const u = await LoginApi.getUserInfo()
    userStore.setUser(u)
    syncProfileForm(u)
  } catch {
    if (userInfo.value?.username) {
      syncProfileForm(userInfo.value)
    }
  } finally {
    userLoading.value = false
  }
}

/* ========== 基本资料 ========== */

const activeTab = ref<'profile' | 'password' | 'setting'>('profile')

const profileFormRef = ref<FormInstance>()
const profileLoading = ref(false)
const profileForm = reactive<LoginApi.UpdateProfileParams>({
  realName: '',
  phone: '',
  email: '',
  department: '',
  title: ''
})

const syncProfileForm = (u: Partial<LoginApi.UserInfo>) => {
  profileForm.realName = u.name || ''
  profileForm.phone = u.phone || ''
  profileForm.email = u.email || ''
  profileForm.department = u.department || ''
  profileForm.title = u.title || ''
}

const profileRules: FormRules = {
  realName: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  email: [
    {
      type: 'email',
      message: '邮箱格式不正确',
      trigger: 'blur'
    }
  ],
  phone: [
    {
      pattern: /^[\d\-+\s()]{6,20}$/,
      message: '手机号格式不正确',
      trigger: 'blur'
    }
  ]
}

const submitProfile = async () => {
  if (!profileFormRef.value) return
  await profileFormRef.value.validate(async (valid) => {
    if (!valid) return
    profileLoading.value = true
    try {
      const u = await LoginApi.updateProfile({
        realName: profileForm.realName || undefined,
        phone: profileForm.phone || undefined,
        email: profileForm.email || undefined,
        department: profileForm.department || undefined,
        title: profileForm.title || undefined
      })
      userStore.setUser(u)
    } catch {
      /* 已弹错误提示 */
    } finally {
      profileLoading.value = false
    }
  })
}

/* ========== 头像上传 ========== */

const avatarUploading = ref(false)
const uploadAvatar = async (opt: UploadRequestOptions) => {
  const f = opt.file
  if (!(f instanceof File)) return
  if (f.size > 5 * 1024 * 1024) {
    ElMessage.warning('头像不能超过 5MB')
    return
  }
  if (!/^image\/(png|jpe?g|webp|bmp)$/i.test(f.type)) {
    ElMessage.warning('仅支持 jpg/jpeg/png/webp/bmp 格式')
    return
  }
  avatarUploading.value = true
  try {
    const res = await LoginApi.uploadAvatar(f)
    userStore.setUser({ ...(userInfo.value as LoginApi.UserInfo), avatar: res.avatarUrl })
  } catch {
    /* 已弹错误提示 */
  } finally {
    avatarUploading.value = false
  }
}

/* ========== 修改密码 ========== */

const pwdFormRef = ref<FormInstance>()
const pwdLoading = ref(false)
const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const pwdRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码长度至少 6 位', trigger: 'blur' },
    {
      validator: (_r, v: string, cb) => {
        if (v && (/^\d+$/.test(v) || /^[A-Za-z]+$/.test(v))) {
          cb(new Error('密码需包含字母与数字'))
        } else {
          cb()
        }
      },
      trigger: 'blur'
    }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_r, v: string, cb) => {
        if (v !== pwdForm.newPassword) cb(new Error('两次输入的新密码不一致'))
        else cb()
      },
      trigger: 'blur'
    }
  ]
}

const submitPassword = async () => {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    pwdLoading.value = true
    try {
      await LoginApi.changePassword({
        oldPassword: pwdForm.oldPassword,
        newPassword: pwdForm.newPassword
      })
      pwdForm.oldPassword = ''
      pwdForm.newPassword = ''
      pwdForm.confirmPassword = ''
      try {
        await ElMessageBox.confirm('密码已更新，是否立即重新登录？', '提示', {
          confirmButtonText: '重新登录',
          cancelButtonText: '稍后',
          type: 'success'
        })
        localStorage.removeItem('huiyan_token')
        localStorage.removeItem('huiyan_refresh_token')
        userStore.clear()
        router.replace('/login')
      } catch {
        /* 用户选择稍后 */
      }
    } catch {
      /* 已弹错误提示 */
    } finally {
      pwdLoading.value = false
    }
  })
}

/* ========== 个性化配置 ========== */

const settingLoading = ref(false)
const settingSaving = ref(false)
const setting = reactive<LoginApi.UserSetting>({
  theme: 'light',
  fontSize: 'normal',
  language: 'zh-CN',
  notifyMessage: true,
  notifyEmail: false,
  notifySms: false,
  notifySound: true
})

const fetchSetting = async () => {
  settingLoading.value = true
  try {
    const s = await LoginApi.getUserSetting()
    Object.assign(setting, s)
  } catch {
    /* 后端不可达时使用默认值 */
  } finally {
    settingLoading.value = false
  }
}

const submitSetting = async () => {
  settingSaving.value = true
  try {
    const s = await LoginApi.updateUserSetting({
      theme: setting.theme,
      fontSize: setting.fontSize,
      language: setting.language,
      notifyMessage: setting.notifyMessage,
      notifyEmail: setting.notifyEmail,
      notifySms: setting.notifySms,
      notifySound: setting.notifySound
    })
    Object.assign(setting, s)
  } catch {
    /* 已弹错误提示 */
  } finally {
    settingSaving.value = false
  }
}

onMounted(() => {
  fetchProfile()
  fetchSetting()
})
</script>

<template>
  <div class="profile-page">
    <main class="profile-main">
      <!-- 顶部用户信息卡 -->
      <div class="user-card" v-loading="userLoading">
        <el-upload
          :show-file-list="false"
          accept="image/png,image/jpeg,image/webp,image/bmp"
          :http-request="uploadAvatar"
          class="avatar-uploader"
        >
          <div class="avatar-wrap">
            <el-avatar
              :size="88"
              :src="userInfo.avatar"
              style="background:#eef4ff;color:#1677ff;font-size:30px"
            >
              {{ avatarLetter }}
            </el-avatar>
            <div class="avatar-mask">
              <el-icon><Camera /></el-icon>
              <span>更换头像</span>
            </div>
            <div v-if="avatarUploading" class="avatar-loading">上传中…</div>
          </div>
        </el-upload>

        <div class="user-info">
          <div class="user-name">{{ displayName }}</div>
          <div class="user-meta">
            <el-tag size="small" type="primary" effect="plain">{{ roleName }}</el-tag>
            <span v-if="userInfo.hospital" class="meta-item">
              <el-icon><Picture /></el-icon>{{ userInfo.hospital }}
            </span>
            <span v-if="userInfo.department" class="meta-item">
              <el-icon><Setting /></el-icon>{{ userInfo.department }}
            </span>
            <span v-if="userInfo.title" class="meta-item">{{ userInfo.title }}</span>
          </div>
          <div v-if="userInfo.lastLoginAt" class="user-last-login">
            上次登录：{{ userInfo.lastLoginAt }}
          </div>
        </div>
      </div>

      <!-- 标签页 -->
      <el-tabs v-model="activeTab" class="profile-tabs">
        <el-tab-pane name="profile">
          <template #label>
            <span class="tab-label"><el-icon><User /></el-icon>基本资料</span>
          </template>
          <div class="card">
            <el-form
              ref="profileFormRef"
              :model="profileForm"
              :rules="profileRules"
              label-width="100px"
              style="max-width: 560px"
            >
              <el-form-item label="账号">
                <el-input :model-value="userInfo.username" disabled />
              </el-form-item>
              <el-form-item label="真实姓名" prop="realName">
                <el-input v-model="profileForm.realName" maxlength="32" />
              </el-form-item>
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="profileForm.phone" maxlength="20" />
              </el-form-item>
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="profileForm.email" maxlength="64" />
              </el-form-item>
              <el-form-item label="所属科室">
                <el-input v-model="profileForm.department" maxlength="64" />
              </el-form-item>
              <el-form-item label="职称">
                <el-input v-model="profileForm.title" maxlength="32" />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  :loading="profileLoading"
                  @click="submitProfile"
                >
                  保存修改
                </el-button>
                <el-button @click="syncProfileForm(userInfo)">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane name="password">
          <template #label>
            <span class="tab-label"><el-icon><Lock /></el-icon>修改密码</span>
          </template>
          <div class="card">
            <el-form
              ref="pwdFormRef"
              :model="pwdForm"
              :rules="pwdRules"
              label-width="120px"
              style="max-width: 520px"
            >
              <el-form-item label="原密码" prop="oldPassword">
                <el-input
                  v-model="pwdForm.oldPassword"
                  type="password"
                  show-password
                  placeholder="请输入当前密码"
                />
              </el-form-item>
              <el-form-item label="新密码" prop="newPassword">
                <el-input
                  v-model="pwdForm.newPassword"
                  type="password"
                  show-password
                  placeholder="字母 + 数字，至少 6 位"
                />
              </el-form-item>
              <el-form-item label="确认新密码" prop="confirmPassword">
                <el-input
                  v-model="pwdForm.confirmPassword"
                  type="password"
                  show-password
                  placeholder="再次输入新密码"
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  :loading="pwdLoading"
                  @click="submitPassword"
                >
                  确认修改
                </el-button>
              </el-form-item>
            </el-form>
            <el-alert
              type="info"
              :closable="false"
              show-icon
              title="安全提示"
              description="密码需包含字母和数字，长度不少于 6 位；修改成功后建议立即重新登录。"
              style="max-width: 520px"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane name="setting">
          <template #label>
            <span class="tab-label"><el-icon><Setting /></el-icon>偏好设置</span>
          </template>
          <div class="card" v-loading="settingLoading">
            <el-form label-width="120px" style="max-width: 560px">
              <el-form-item label="界面主题">
                <el-radio-group v-model="setting.theme">
                  <el-radio-button value="light">浅色</el-radio-button>
                  <el-radio-button value="dark">深色</el-radio-button>
                  <el-radio-button value="auto">跟随系统</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="字体大小">
                <el-radio-group v-model="setting.fontSize">
                  <el-radio-button value="small">小</el-radio-button>
                  <el-radio-button value="normal">中</el-radio-button>
                  <el-radio-button value="large">大</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="界面语言">
                <el-select v-model="setting.language" style="width: 200px">
                  <el-option label="简体中文" value="zh-CN" />
                  <el-option label="English" value="en-US" />
                </el-select>
              </el-form-item>
              <el-divider content-position="left">消息通知</el-divider>
              <el-form-item label="站内消息">
                <el-switch v-model="setting.notifyMessage" />
              </el-form-item>
              <el-form-item label="邮件通知">
                <el-switch v-model="setting.notifyEmail" />
              </el-form-item>
              <el-form-item label="短信通知">
                <el-switch v-model="setting.notifySms" />
              </el-form-item>
              <el-form-item label="提示音">
                <el-switch v-model="setting.notifySound" />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  :loading="settingSaving"
                  @click="submitSetting"
                >
                  保存配置
                </el-button>
                <el-button @click="fetchSetting">刷新</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>
      </el-tabs>
    </main>
  </div>
</template>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: #f5f6fa;
  display: flex;
  flex-direction: column;
}

.profile-header {
  height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e5e6eb;
  display: flex;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.divider {
  width: 1px;
  height: 18px;
  background: #e5e6eb;
}
.page-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}

.profile-main {
  flex: 1;
  padding: 20px 24px;
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

.user-card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 22px;
}

.avatar-uploader {
  display: inline-block;
}
.avatar-wrap {
  position: relative;
  width: 88px;
  height: 88px;
  border-radius: 50%;
  overflow: hidden;
  cursor: pointer;
}
.avatar-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  display: none;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  gap: 4px;
}
.avatar-wrap:hover .avatar-mask {
  display: flex;
}
.avatar-loading {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.user-info {
  flex: 1;
  min-width: 0;
}
.user-name {
  font-size: 20px;
  font-weight: 700;
  color: #1d2129;
  margin-bottom: 8px;
}
.user-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
  color: #4e5969;
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.user-last-login {
  font-size: 12px;
  color: #86909c;
  margin-top: 8px;
}

.profile-tabs {
  background: transparent;
}
:deep(.el-tabs__header) {
  margin-bottom: 0;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px 12px 0 0;
  padding: 0 8px;
}
:deep(.el-tabs__content) {
  padding: 0;
}

.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-top: none;
  border-radius: 0 0 12px 12px;
  padding: 24px 28px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
</style>
