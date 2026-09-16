<script setup lang="ts">
/**
 * 申请学员账号（独立页，不复用病患「立即注册」）
 */
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Iphone, User, OfficeBuilding, ChatLineRound, Search } from '@element-plus/icons-vue'
import { StudentAppApi } from '@/api'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const submitted = ref(false)

const form = reactive<StudentAppApi.StudentAppCreate>({
  realName: '',
  phone: '',
  department: '',
  reason: ''
})

const phoneReg = /^1[3-9]\d{9}$/

const rules: FormRules = {
  realName: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
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
  department: [{ required: true, message: '请输入所在科室', trigger: 'blur' }],
  reason: [
    { required: true, message: '请填写申请理由', trigger: 'blur' },
    { min: 4, message: '理由至少 4 个字', trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      await StudentAppApi.applyStudentAccount({ ...form })
      submitted.value = true
    } catch {
      /* 拦截器已弹错 */
    } finally {
      submitting.value = false
    }
  })
}

const queryPhone = ref('')
const queryLoading = ref(false)
const queryResult = ref<StudentAppApi.StudentAppStatusQuery | null>(null)

const STATUS_TEXT: Record<string, string> = {
  PENDING: '待审核',
  APPROVED: '已通过，可用学生入口登录',
  REJECTED: '已驳回'
}

const handleQuery = async () => {
  const phone = queryPhone.value.trim()
  if (!phoneReg.test(phone)) {
    ElMessage.warning('请输入 11 位手机号查询')
    return
  }
  queryLoading.value = true
  try {
    queryResult.value = await StudentAppApi.queryStudentAppStatus(phone)
    if (!queryResult.value?.found) {
      ElMessage.info('未查到该手机号的申请记录')
    }
  } catch {
    queryResult.value = null
  } finally {
    queryLoading.value = false
  }
}

const goLogin = () => router.push({ path: '/login' })
</script>

<template>
  <div class="apply-page">
    <div class="apply-bg">
      <div class="bg-circle c1"></div>
      <div class="bg-circle c2"></div>
    </div>
    <div class="apply-container">
      <div class="apply-card">
        <div class="card-header">
          <h2>申请学员账号</h2>
          <p>填写资料后由管理员审核开户，通过后会短信告知登录账号与初密。</p>
        </div>

        <el-alert
          v-if="submitted"
          type="success"
          :closable="false"
          show-icon
          title="申请已提交，请等待管理员审核。通过或驳回都会短信通知该手机号。"
          style="margin-bottom: 18px"
        />

        <el-form
          v-if="!submitted"
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          label-position="top"
        >
          <el-form-item label="姓名" prop="realName">
            <el-input v-model="form.realName" maxlength="32" :prefix-icon="User" placeholder="真实姓名" />
          </el-form-item>
          <el-form-item label="手机号" prop="phone">
            <el-input v-model="form.phone" maxlength="11" :prefix-icon="Iphone" placeholder="11 位手机号，审核结果将发至此号码" />
          </el-form-item>
          <el-form-item label="科室" prop="department">
            <el-input v-model="form.department" maxlength="64" :prefix-icon="OfficeBuilding" placeholder="如：眼科 / 内分泌科" />
          </el-form-item>
          <el-form-item label="申请理由" prop="reason">
            <el-input
              v-model="form.reason"
              type="textarea"
              :rows="4"
              maxlength="500"
              show-word-limit
              :prefix-icon="ChatLineRound"
              placeholder="说明培训需求或所在医院 / 年级"
            />
          </el-form-item>
          <el-button type="primary" size="large" class="submit-btn" :loading="submitting" @click="handleSubmit">
            提交申请
          </el-button>
        </el-form>

        <div class="query-box">
          <div class="query-title">查询审核进度</div>
          <div class="query-row">
            <el-input v-model="queryPhone" maxlength="11" placeholder="输入申请时的手机号" />
            <el-button :icon="Search" :loading="queryLoading" @click="handleQuery">查询</el-button>
          </div>
          <div v-if="queryResult?.found" class="query-result">
            <div>申请人：{{ queryResult.realName }}</div>
            <div>状态：{{ STATUS_TEXT[queryResult.status] || queryResult.status }}</div>
            <div v-if="queryResult.accountUsername">账号：{{ queryResult.accountUsername }}（请从学生入口登录）</div>
            <div v-if="queryResult.reviewComment">驳回理由：{{ queryResult.reviewComment }}</div>
          </div>
        </div>

        <div class="extra">
          已有学员账号？
          <a class="link" @click="goLogin">返回学生入口登录</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.apply-page {
  position: relative;
  width: 100vw;
  min-height: 100vh;
  background: linear-gradient(135deg, #eef4ff 0%, #f5f9ff 60%, #ffffff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 0;
}
.apply-bg { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.bg-circle { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.4; }
.c1 { width: 480px; height: 480px; background: #c7dbff; top: -120px; left: -100px; }
.c2 { width: 380px; height: 380px; background: #d6f0ff; bottom: -80px; right: -60px; }
.apply-container { position: relative; z-index: 2; width: 520px; max-width: 92vw; }
.apply-card {
  background: #fff;
  border-radius: 16px;
  padding: 36px 40px 32px;
  box-shadow: 0 20px 60px rgba(22, 119, 255, 0.12);
}
.card-header { margin-bottom: 20px; }
.card-header h2 { margin: 0; font-size: 24px; font-weight: 700; color: #1d2129; }
.card-header p { margin: 8px 0 0; font-size: 13px; color: #86909c; line-height: 1.6; }
.submit-btn { width: 100%; letter-spacing: 4px; }
.query-box {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px dashed #e5e6eb;
}
.query-title { font-size: 13px; color: #4e5969; margin-bottom: 8px; }
.query-row { display: flex; gap: 8px; }
.query-result {
  margin-top: 10px;
  font-size: 13px;
  color: #1d2129;
  line-height: 1.8;
  background: #f7f8fa;
  border-radius: 8px;
  padding: 10px 12px;
}
.extra { margin-top: 18px; text-align: center; color: #4e5969; font-size: 13px; }
.link { color: #1677ff; cursor: pointer; margin-left: 4px; }
</style>
