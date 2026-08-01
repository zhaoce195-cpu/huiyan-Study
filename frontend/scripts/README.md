# 阅片内核回归自检

替换为 Cornerstone3D 之后，阅片画布的正确性无法只靠类型检查保证：
坐标算错、影像没解码出来、旧视口快照被按新语义硬套，
这些都能通过编译。所以用无头浏览器实跑。

前置：dev server 在 5178（`npx vite --port 5178`）。

```bash
# 内核层：web: 加载器、坐标往返、映射是否跟随视口
node scripts/check_viewport.mjs 5178

# 组件层：渲染就绪、标注绘制、视口快照兼容、工具切换
node scripts/check_station.mjs 5178

# DICOM 链路：wadors 取像 + 元数据自注册 + 解码
node scripts/check_dicom.mjs <studyUid> <seriesUid> <sopUid> <token>
```

自检页 `/spike/viewport-check`、`/spike/station-check` 标了 public，
只渲染静态图、不读业务数据，因此能在无登录态下跑。

注意「往返自洽」不等于「映射正确」：映射退化成恒等函数时往返同样完美，
所以脚本里专门有「映射不是恒等函数」「映射跟随缩放变化」两条反向检查。
