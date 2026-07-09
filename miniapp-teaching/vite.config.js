import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

// 本工程为「根目录布局」（pages.json/manifest.json 在项目根，便于 HBuilderX 直接打开）。
// uni-app CLI 默认源目录是 src/，编译时需在进程级设置 UNI_INPUT_DIR 指向项目根。
// 已在 package.json 的 scripts 中用 cross-env 注入，无需手动设置。
export default defineConfig({
  plugins: [uni()],
})
