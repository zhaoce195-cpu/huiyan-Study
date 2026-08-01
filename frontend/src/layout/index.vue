<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useLogout } from '@/composables/useLogout'

/** 传输是否加密：按实际连接判定，避免出现无法核对的安全声明 */
const isSecureConnection = window.location.protocol === 'https:'


const router = useRouter()
const userStore = useUserStore()
const { logout } = useLogout()

const userInfo = computed(() => userStore.userInfo)
const displayName = computed(() => userStore.displayName)
const isTrainee = computed(() => userStore.isTrainee)
const isPatient = computed(() => userStore.isPatient)
const roleName = computed(() => userStore.roleName)

/* ========== 权限控制 ==========
 * patient — 跳转个人报告页（layout 不展示）
 * trainee — 仅可访问医学培训端
 * admin / doctor — 双端可访问
 */
const canAccessScreening = computed(() => userStore.canAccessScreening)
const canAccessTraining = computed(() => userStore.canAccessTraining)

const goScreening = () => {
  if (!canAccessScreening.value) {
    ElMessage.warning('当前账号无体检筛查端访问权限')
    return
  }
  router.push('/screening')
}
const goTraining = () => {
  if (!canAccessTraining.value) {
    ElMessage.warning('当前账号无医学培训端访问权限')
    return
  }
  router.push('/training')
}
const goProfile = () => router.push('/profile')

onMounted(() => {
  // 体检者直接跳转报告页（理论上路由守卫已拦截，此处兜底）
  if (isPatient.value) {
    router.replace('/patient/reports')
    return
  }
  userStore.fetchProfile()
})
</script>

<template>
  <div class="home-page">
    <header class="home-header">
      <div class="brand">
        <svg viewBox="0 0 48 48" width="36" height="36">
          <circle cx="24" cy="24" r="22" fill="#1677ff" opacity="0.14" />
          <circle cx="24" cy="24" r="14" fill="none" stroke="#1677ff" stroke-width="2.5" />
          <circle cx="24" cy="24" r="6" fill="#1677ff" />
          <circle cx="24" cy="24" r="2.5" fill="#fff" />
        </svg>
        <div class="brand-name">慧眼医疗云平台 <span>V2.0</span></div>
      </div>
      <div class="user-area">
        <el-dropdown trigger="hover">
          <span class="welcome">
            <el-avatar
              :size="28"
              :src="userInfo.avatar"
              style="background:#eef4ff;color:#1677ff;font-size:12px;margin-right:8px"
            >
              {{ displayName.charAt(0) }}
            </el-avatar>
            欢迎，{{ displayName }}
            <el-tag size="small" type="primary" effect="plain" style="margin-left:8px">
              {{ roleName }}
            </el-tag>
            <el-icon style="margin-left:4px"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                {{ userInfo.hospital || '未关联机构' }}
              </el-dropdown-item>
              <el-dropdown-item disabled>
                {{ userInfo.department || '未关联科室' }}
              </el-dropdown-item>
              <el-dropdown-item divided @click="goProfile">
                个人中心
              </el-dropdown-item>
              <el-dropdown-item @click="logout">
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button text type="primary" @click="logout">退出登录</el-button>
      </div>
    </header>

    <main class="home-main">
      <div class="hero">
        <h1>请选择您的工作场景</h1>
        <p v-if="isTrainee">
          学员账号 · 仅可访问医学培训端 · 完成临床阅片标准化训练
        </p>
        <p v-else>
          双端口物理隔离 · 共享统一登录与权限 · 所有功能模块已嵌入对应端口侧边栏
        </p>
      </div>

      <div class="scene-cards" :class="{ 'single-scene': isTrainee }">
        <div
          v-if="canAccessScreening"
          class="scene-card light"
          @click="goScreening"
        >
          <div class="card-tag">SCENE 01</div>
          <div class="card-body">
            <div class="card-icon icon-light">
              <svg viewBox="0 0 64 64" width="56" height="56" fill="none">
                <circle cx="32" cy="32" r="26" stroke="#1677ff" stroke-width="3" />
                <circle cx="32" cy="32" r="14" stroke="#1677ff" stroke-width="2" />
                <circle cx="32" cy="32" r="5" fill="#1677ff" />
                <path d="M14 32 H50" stroke="#1677ff" stroke-width="1.5" stroke-dasharray="2 3" />
              </svg>
            </div>
            <h2>体检筛查端</h2>
            <p class="desc">面向体检中心 / 基层医疗 · 浅色主题 · 侧边栏一站式导航</p>
            <ul class="feature-list">
              <li>批量上传与 AI 一键分级</li>
              <li>红黄绿三色风险分级</li>
              <li>筛查列表统一台账管理</li>
              <li>报告导出与个人中心</li>
            </ul>
          </div>
          <div class="card-footer">
            <span class="tag-pill blue">浅色主题</span>
            <span class="enter">进入工作台 →</span>
          </div>
        </div>

        <div
          v-if="canAccessTraining"
          class="scene-card dark"
          @click="goTraining"
        >
          <div class="card-tag">SCENE {{ isTrainee ? '01' : '02' }}</div>
          <div class="card-body">
            <div class="card-icon icon-dark">
              <svg viewBox="0 0 64 64" width="56" height="56" fill="none">
                <rect x="6" y="14" width="52" height="36" rx="4" stroke="#4091ff" stroke-width="2.5" />
                <path d="M14 32 L26 26 L34 36 L42 30 L50 38" stroke="#4091ff" stroke-width="2" fill="none" />
                <circle cx="42" cy="30" r="3" fill="#4091ff" />
              </svg>
            </div>
            <h2>医学培训端</h2>
            <p class="desc">面向住培医师 / 临床教学 · 深色主题 · 全模块统一侧边栏</p>
            <ul class="feature-list">
              <li>病例库检索 · 影像阅片标注</li>
              <li>自主练习 · 自动评分 · 金标准对比</li>
              <li>学习资料 · 收藏 · 笔记联动复盘</li>
              <li>教师/管理员可见管理后台</li>
            </ul>
          </div>
          <div class="card-footer">
            <span class="tag-pill purple">深色主题</span>
            <span class="enter">进入培训系统 →</span>
          </div>
        </div>
      </div>

      <!-- 所有功能模块（含平台管理后台）已嵌入双端口侧边栏，首页仅保留两个端口入口 -->
    </main>

    <footer class="home-footer">
      <div>慧眼医疗 © 2026</div>
      <!--
        合规声明整改（报告 P0：入口为明文 HTTP，却展示「数据加密传输」）。
        传输状态改为按当前连接实时判定，声明因此永远可被用户自行核对；
        原「国家三类医疗器械软件备案 / 符合《医疗器械数据完整性要求》」
        属不可追溯表述，已移除——若确已取得注册证，请填回具体证书编号。
      -->
      <div v-if="isSecureConnection" class="secure-ok">
        已启用 HTTPS 加密传输
      </div>
      <div v-else class="secure-warn">
        当前为非加密连接（HTTP），请联系管理员启用 HTTPS 后再传输患者相关数据
      </div>
      <div>AI 结果仅供教学与辅助参考，不作为临床诊断依据</div>
    </footer>
  </div>
</template>

<style scoped>
.home-footer .secure-ok {
  color: #2f9e44;
}
.home-footer .secure-warn {
  color: #c92a2a;
  font-weight: 600;
}

.home-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f5f9ff 0%, #ffffff 50%, #f8f9fb 100%);
  display: flex;
  flex-direction: column;
}

.home-header {
  height: 64px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #e5e6eb;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: #1d2129;
  letter-spacing: 1.2px;
}
.brand-name span {
  color: #1677ff;
  font-size: 13px;
  margin-left: 6px;
  font-weight: 600;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 14px;
}
.welcome {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  color: #4e5969;
  cursor: pointer;
  user-select: none;
}

.home-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 32px 40px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
}
.hero {
  text-align: center;
  margin-bottom: 48px;
}
.hero h1 {
  margin: 0;
  font-size: 36px;
  font-weight: 700;
  color: #1d2129;
  letter-spacing: 2px;
}
.hero p {
  margin: 12px 0 0;
  font-size: 15px;
  color: #86909c;
  letter-spacing: 1px;
}

.scene-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  width: 100%;
}
.scene-cards.single-scene {
  grid-template-columns: minmax(0, 560px);
  justify-content: center;
}

.scene-card {
  position: relative;
  border-radius: 20px;
  padding: 32px 32px 24px;
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 440px;
}
.scene-card:hover {
  transform: translateY(-6px);
}

.scene-card.light {
  background: #fff;
  border: 1px solid #e6effe;
  box-shadow: 0 16px 50px rgba(22, 119, 255, 0.1);
}
.scene-card.light:hover {
  box-shadow: 0 24px 70px rgba(22, 119, 255, 0.18);
}

.scene-card.dark {
  background: linear-gradient(135deg, #1a1f2c 0%, #141414 100%);
  border: 1px solid #2a2a2a;
  color: #e5e6eb;
  box-shadow: 0 16px 50px rgba(0, 0, 0, 0.25);
}
.scene-card.dark:hover {
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.45);
  border-color: #4091ff;
}

.card-tag {
  position: absolute;
  top: 24px;
  right: 28px;
  font-size: 12px;
  letter-spacing: 2px;
  color: #c9cdd4;
  font-weight: 600;
}
.scene-card.dark .card-tag {
  color: #4091ff;
  opacity: 0.7;
}

.card-body {
  flex: 1;
}
.card-icon {
  width: 80px;
  height: 80px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
}
.icon-light {
  background: #eef4ff;
}
.icon-dark {
  background: rgba(64, 145, 255, 0.12);
  border: 1px solid rgba(64, 145, 255, 0.3);
}

.scene-card h2 {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 1.5px;
}
.scene-card.light h2 {
  color: #1d2129;
}
.scene-card.dark h2 {
  color: #fff;
}
.desc {
  margin: 0 0 20px;
  font-size: 14px;
  color: #86909c;
  line-height: 1.7;
}
.feature-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.feature-list li {
  font-size: 13px;
  color: #4e5969;
  padding-left: 20px;
  position: relative;
}
.feature-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1677ff;
  opacity: 0.6;
}
.scene-card.dark .feature-list li {
  color: #c9cdd4;
}
.scene-card.dark .feature-list li::before {
  background: #4091ff;
}

.card-footer {
  margin-top: 22px;
  padding-top: 20px;
  border-top: 1px dashed #e5e6eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.scene-card.dark .card-footer {
  border-top-color: #2a2a2a;
}
.tag-pill {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.tag-pill.blue {
  background: #eef4ff;
  color: #1677ff;
}
.tag-pill.purple {
  background: rgba(64, 145, 255, 0.15);
  color: #4091ff;
}
.enter {
  font-size: 14px;
  font-weight: 600;
  color: #1677ff;
}
.scene-card.dark .enter {
  color: #4091ff;
}

.home-footer {
  padding: 24px 32px;
  text-align: center;
  font-size: 12px;
  color: #c9cdd4;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

@media (max-width: 960px) {
  .scene-cards {
    grid-template-columns: 1fr;
  }
}

.extra-entries {
  margin-top: 28px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  justify-content: center;
}

.entry-tile {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 22px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  color: #4e5969;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.entry-tile:hover {
  border-color: #1677ff;
  box-shadow: 0 2px 12px rgba(22, 119, 255, 0.12);
  color: #1677ff;
}
.entry-icon {
  font-size: 16px;
}
.entry-sub {
  font-size: 12px;
  color: #c9cdd4;
}
.entry-arrow {
  margin-left: 4px;
  font-weight: 600;
}
</style>
