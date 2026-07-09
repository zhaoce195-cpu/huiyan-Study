import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import compression from 'vite-plugin-compression'

// https://vite.dev/config/
export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE_URL || '/api'
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'
  const isProd = command === 'build'

  return {
    base: env.VITE_PUBLIC_BASE || '/',

    plugins: [
      vue(),
      // 仅生产构建时启用 gzip 压缩，输出 .gz 文件供 Nginx 直接返回
      isProd &&
        compression({
          algorithm: 'gzip',
          ext: '.gz',
          threshold: 10240,
          deleteOriginFile: false
        }),
      // 同时输出 brotli 压缩文件（更高压缩比，现代浏览器都支持）
      isProd &&
        compression({
          algorithm: 'brotliCompress',
          ext: '.br',
          threshold: 10240,
          deleteOriginFile: false
        })
    ],

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },

    server: {
      port: 5174,
      open: true,
      host: '0.0.0.0',
      proxy: {
        [apiBase]: {
          target: apiTarget,
          changeOrigin: true
        },
        // 后端静态资源（头像 / 眼底图 / 上传文件等）
        '/static': {
          target: apiTarget,
          changeOrigin: true
        }
      }
    },

    preview: {
      port: 4173,
      host: '0.0.0.0',
      proxy: {
        [apiBase]: {
          target: apiTarget,
          changeOrigin: true
        },
        '/static': {
          target: apiTarget,
          changeOrigin: true
        }
      }
    },

    build: {
      target: 'es2018',
      outDir: 'dist',
      assetsDir: 'assets',
      // 关闭 sourcemap，节省体积；生产排错可单独开启
      sourcemap: false,
      cssCodeSplit: true,
      reportCompressedSize: false,
      chunkSizeWarningLimit: 1500,

      // 使用 terser 做更彻底的压缩
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: true,
          drop_debugger: true,
          pure_funcs: ['console.log', 'console.debug', 'console.info']
        },
        format: {
          comments: false
        }
      },

      // rollup 分包：核心库分离，提高浏览器缓存命中率
      rollupOptions: {
        output: {
          // 静态资源命名规则（含 hash，便于强缓存）
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: ({ name }) => {
            if (/\.(png|jpe?g|gif|svg|webp|ico)$/i.test(name || '')) {
              return 'assets/img/[name]-[hash][extname]'
            }
            if (/\.(woff2?|eot|ttf|otf)$/i.test(name || '')) {
              return 'assets/fonts/[name]-[hash][extname]'
            }
            if (/\.css$/i.test(name || '')) {
              return 'assets/css/[name]-[hash][extname]'
            }
            return 'assets/[name]-[hash][extname]'
          },
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('element-plus')) return 'vendor-element-plus'
              if (id.includes('@element-plus/icons-vue')) return 'vendor-icons'
              if (id.includes('vue-router') || id.includes('pinia') || /[\\/]vue[\\/]/.test(id)) {
                return 'vendor-vue'
              }
              if (id.includes('axios')) return 'vendor-axios'
              return 'vendor'
            }
          }
        }
      }
    }
  }
})
