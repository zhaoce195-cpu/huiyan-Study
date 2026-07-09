<script setup lang="ts">
import { reactive, ref, computed, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Iphone, Lock, Key, User } from '@element-plus/icons-vue'
import { PatientApi } from '@/api'

const router = useRouter()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive<PatientApi.RegisterParams & { confirmPassword: string }>({
  phone: '',
  password: '',
  confirmPassword: '',
  code: '',
  realName: ''
})

const phoneReg = /^1[3-9]\d{9}$/

const rules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (!v) return cb(new Error('请输入手机号'))
        if (!phoneReg.test(v)) return cb(new Error('请输入 11 位有效手机号'))
        cb()
      },
      trigger: 'blur'
    }
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, max: 8, message: '验证码长度有误', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (v !== form.password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur'
    }
  ]
}

/* ========== 验证码倒计时 ========== */
const COUNTDOWN_SEC = 60
const countdown = ref(0)
let timer: number | null = null
const sending = ref(false)

const canSendCode = computed(() => countdown.value <= 0 && !sending.value)
const codeBtnText = computed(() =>
  countdown.value > 0 ? `${countdown.value}s 后重发` : '获取验证码'
)

const startCountdown = () => {
  countdown.value = COUNTDOWN_SEC
  if (timer) window.clearInterval(timer)
  timer = window.setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0 && timer) {
      window.clearInterval(timer)
      timer = null
    }
  }, 1000)
}

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

const handleSendCode = async () => {
  if (!phoneReg.test(form.phone)) {
    ElMessage.warning('请先输入正确的手机号')
    return
  }
  sending.value = true
  try {
    const res = await PatientApi.sendCode({ phone: form.phone })
    startCountdown()
    // 模拟环境直接展示验证码，便于联调
    if (res?.code) {
      ElMessage.info(`模拟验证码：${res.code}（${Math.floor(res.expiresIn / 60)} 分钟内有效）`)
    }
  } finally {
    sending.value = false
  }
}

/* ========== 提交注册 ========== */
const handleRegister = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      await PatientApi.register({
        phone: form.phone,
        password: form.password,
        code: form.code,
        realName: form.realName || undefined
      })
      ElMessage.success('注册成功，请登录')
      router.replace({ path: '/login', query: { username: form.phone } })
    } finally {
      submitting.value = false
    }
  })
}

const goLogin = () => router.push('/login')
</script>

<template>
  <div class="register-page">
    <div class="register-bg">
      <div class="bg-circle c1"></div>
      <div class="bg-circle c2"></div>
      <div class="bg-circle c3"></div>
    </div>

    <div class="register-container">
      <div class="register-card">
        <div class="card-header">
          <h2>欢迎注册</h2>
          <p>注册成功后可使用手机号登录，查询本人体检报告</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          @keyup.enter="handleRegister"
        >
          <el-form-item prop="phone">
            <el-input
              v-model="form.phone"
              placeholder="请输入手机号"
              :prefix-icon="Iphone"
              maxlength="11"
              clearable
            />
          </el-form-item>

          <el-form-item prop="code">
            <div class="code-row">
              <el-input
                v-model="form.code"
                placeholder="短信验证码"
                :prefix-icon="Key"
                maxlength="8"
                clearable
              />
              <el-button
                type="primary"
                class="code-btn"
                :disabled="!canSendCode"
                :loading="sending"
                @click="handleSendCode"
              >
                {{ codeBtnText }}
              </el-button>
            </div>
          </el-form-item>

          <el-form-item prop="realName">
            <el-input
              v-model="form.realName"
              placeholder="姓名（可选）"
              :prefix-icon="User"
              maxlength="32"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="设置登录密码（不少于 6 位）"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="再次输入密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            class="register-btn"
            :loading="submitting"
            @click="handleRegister"
          >
            立 即 注 册
          </el-button>

          <div class="extra">
            已有账号？
            <a class="link" @click="goLogin">返回登录</a>
          </div>

          <div class="tip">
            体检病患账号注册成功后，可在【我的体检报告】查看本人就诊记录与影像。
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.register-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: linear-gradient(135deg, #eef4ff 0%, #f5f9ff 60%, #ffffff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.register-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.bg-circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
}
.c1 { width: 480px; height: 480px; background: #c7dbff; top: -120px; left: -100px; }
.c2 { width: 380px; height: 380px; background: #d6f0ff; bottom: -80px; right: -60px; }
.c3 { width: 240px; height: 240px; background: #e6f7ec; top: 60%; left: 40%; }

.register-container {
  position: relative;
  z-index: 2;
  width: 480px;
  max-width: 92vw;
}
.register-card {
  background: #fff;
  border-radius: 16px;
  padding: 36px 40px 32px;
  box-shadow: 0 20px 60px rgba(22, 119, 255, 0.12);
}
.card-header {
  margin-bottom: 24px;
}
.card-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1d2129;
  letter-spacing: 1px;
}
.card-header p {
  margin: 8px 0 0;
  font-size: 13px;
  color: #86909c;
}
.code-row {
  display: flex;
  width: 100%;
  gap: 8px;
}
.code-row .el-input {
  flex: 1;
}
.code-btn {
  width: 130px;
  flex-shrink: 0;
}
.register-btn {
  width: 100%;
  margin-top: 4px;
  letter-spacing: 6px;
}
.extra {
  margin-top: 16px;
  text-align: center;
  color: #4e5969;
  font-size: 13px;
}
.link {
  color: #1677ff;
  cursor: pointer;
  margin-left: 4px;
}
.tip {
  margin-top: 18px;
  font-size: 12px;
  color: #86909c;
  text-align: center;
  line-height: 1.7;
  padding-top: 12px;
  border-top: 1px dashed #e5e6eb;
}
</style>
