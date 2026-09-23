<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadRequestOptions
} from 'element-plus'
import { Lock, User, Setting, Camera, Bell } from '@element-plus/icons-vue'
import { LoginApi, RotationApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { applyFontSize } from '@/utils/appearance'
import NotificationInbox from '@/views/notices/NotificationInbox.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const forcePwd = computed(
  () => route.query.forcePwd === '1' || !!userStore.userInfo.mustChangePassword
)

/* ========== 当前用户信息 ========== */

const userInfo = computed<Partial<LoginApi.UserInfo>>(() => userStore.userInfo)
const userLoading = ref(false)

const isStudent = computed(() => userStore.isTrainee)
const isStaff = computed(() => userStore.isAdmin || userStore.isDoctor)
const rotationText = ref('')
const studyYearText = ref('')
const rotationBatchText = ref('')
const mentorGroupText = ref('')
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

const activeTab = ref<'profile' | 'password' | 'setting' | 'notices'>('profile')

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
        department: isStaff.value ? profileForm.department || undefined : undefined,
        title: isStaff.value ? profileForm.title || undefined : undefined
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
      userStore.setUser({
        ...(userInfo.value as LoginApi.UserInfo),
        mustChangePassword: false
      })
      if (forcePwd.value) {
        await ElMessageBox.alert('密码已更新，请使用新密码重新登录', '修改成功', {
          confirmButtonText: '去登录',
          type: 'success'
        })
        localStorage.removeItem('huiyan_token')
        localStorage.removeItem('huiyan_refresh_token')
        userStore.clear()
        router.replace('/login')
        return
      }
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
    applyFontSize(setting.fontSize)
  } catch {
    /* 后端不可达时使用默认值 */
  } finally {
    settingLoading.value = false
  }
}

// 字号即时预览：选完就能看出区别，不用先保存再猜有没有生效
watch(() => setting.fontSize, (v) => applyFontSize(v))

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
    applyFontSize(setting.fontSize)
    // 原来保存完悄无声息，用户只能靠刷新去猜存没存上
    ElMessage.success('配置已保存')
  } catch {
    /* 已弹错误提示 */
  } finally {
    settingSaving.value = false
  }
}

watch(forcePwd, (v) => {
  if (v) activeTab.value = 'password'
}, { immediate: true })

watch(
  () => route.query.tab,
  (tab) => {
    if (forcePwd.value) return
    if (tab === 'notices') activeTab.value = 'notices'
  },
  { immediate: true }
)

watch(activeTab, (v) => {
  if (forcePwd.value && v !== 'password') {
    activeTab.value = 'password'
    ElMessage.warning('请先修改临时密码')
  }
})

onMounted(() => {
  fetchProfile()
  fetchSetting()
  if (isStudent.value) {
    RotationApi.getHome()
      .then((home) => {
        if (home.role !== 'student' || !home.rotation) {
          studyYearText.value = home.role === 'student' ? home.studyYear : ''
          rotationBatchText.value = home.role === 'student' ? home.rotationBatch : ''
          mentorGroupText.value = home.role === 'student' ? home.mentorGroup : ''
          return
        }
        const due = home.rotation.dueOn ? `，截止 ${home.rotation.dueOn}` : ''
        rotationText.value = `${home.rotation.title}${due}`
        studyYearText.value = home.studyYear
        rotationBatchText.value = home.rotationBatch
        mentorGroupText.value = home.mentorGroup
      })
      .catch(() => {
        rotationText.value = ''
      })
  }
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
            <span v-if="isStaff && userInfo.department" class="meta-item">
              <el-icon><Setting /></el-icon>{{ userInfo.department }}
            </span>
            <span v-if="isStaff && userInfo.title" class="meta-item">{{ userInfo.title }}</span>
            <span v-if="isStudent && rotationText" class="meta-item">{{ rotationText }}</span>
          </div>
          <div v-if="userInfo.lastLoginAt" class="user-last-login">
            上次登录：{{ userInfo.lastLoginAt }}
          </div>
          <el-button
            v-if="userStore.isTrainee"
            size="small"
            type="primary"
            plain
            style="margin-top: 10px"
            @click="router.push('/training/my-reviews')"
          >
            查看教师评定
          </el-button>
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
              <el-form-item v-if="isStaff" label="所属科室">
                <el-input v-model="profileForm.department" maxlength="64" />
              </el-form-item>
              <el-form-item v-if="isStaff" label="职称">
                <el-input v-model="profileForm.title" maxlength="32" placeholder="如副主任医师" />
              </el-form-item>
              <el-form-item v-if="isStudent" label="身份">
                <el-input model-value="学员" disabled />
              </el-form-item>
              <el-form-item v-if="isStudent" label="年级">
                <el-input :model-value="studyYearText || '未分组'" disabled />
              </el-form-item>
              <el-form-item v-if="isStudent" label="轮转批次">
                <el-input :model-value="rotationBatchText || '未分组'" disabled />
              </el-form-item>
              <el-form-item v-if="isStudent" label="带教组">
                <el-input :model-value="mentorGroupText || '未分组'" disabled />
              </el-form-item>
              <el-form-item v-if="isStudent" label="当前轮转">
                <el-input :model-value="rotationText || '老师尚未布置轮转'" disabled />
                <el-button link type="primary" @click="router.push('/training/home')">
                  查看今日任务
                </el-button>
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
            <el-alert
              v-if="forcePwd"
              type="warning"
              :closable="false"
              show-icon
              title="管理员为该账号生成了临时密码，必须先改密才能继续使用系统。"
              style="margin-bottom: 16px"
            />
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

        <el-tab-pane name="notices">
          <template #label>
            <span class="tab-label"><el-icon><Bell /></el-icon>通知</span>
          </template>
          <NotificationInbox />
        </el-tab-pane>

        <el-tab-pane name="setting">
          <template #label>
            <span class="tab-label"><el-icon><Setting /></el-icon>偏好设置</span>
          </template>
          <div class="card" v-loading="settingLoading">
            <el-form label-width="120px" style="max-width: 560px">
              <!--
                界面主题 / 界面语言 / 消息通知开关暂时下线。
                这三块后端存得下，但前端从来没有消费过：全站没有暗色主题实现、
                没引入任何 i18n、通知开关也没有任何代码读取，改了必然「没反应」
                （三份用户测试报告都点名了这条）。等真正实现时再放出来，
                后端接口和字段保持不变，恢复只需要把这几段取消注释。
              -->
              <el-form-item label="字体大小">
                <el-radio-group v-model="setting.fontSize">
                  <el-radio-button value="small">小</el-radio-button>
                  <el-radio-button value="normal">中</el-radio-button>
                  <el-radio-button value="large">大</el-radio-button>
                </el-radio-group>
                <div class="setting-hint">选中即时生效，保存后下次登录仍沿用</div>
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

.setting-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.6;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
</style>
