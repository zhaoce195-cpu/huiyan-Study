import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/user'
import { drGradeColor } from './utils/dr-format'
import { initAppearance } from './utils/appearance'
import './styles/var.css'

// 字号偏好先于挂载生效，避免默认字号闪一下再跳到用户设置
initAppearance()

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component as any)
}

/**
 * 全局 directive: v-dr-color
 * 用法：<span v-dr-color="r.drGrade">DR {{ r.drGrade }} 级</span>
 * 给元素的文字着色为对应 DR 等级颜色
 */
app.directive('dr-color', {
  mounted(el, binding) {
    el.style.color = drGradeColor(binding.value)
  },
  updated(el, binding) {
    el.style.color = drGradeColor(binding.value)
  },
})

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// Pinia 安装后立即用 localStorage 缓存初始化用户 store；后台异步刷新 profile
useUserStore().init()

app.mount('#app')
