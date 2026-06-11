# Annotator 组件清单

## topbar
- 原始 HTML 位置: `module/server/web/annotator/index.html` 顶部 `<header class="topbar">`
- 原始 CSS 位置: `module/server/web/annotator/static/style.css` 中 `.topbar*` 规则
- 原始 JS 位置: `module/server/web/annotator/static/layout-ui.js`（主题切换与头部控件）

## left-window
- 原始 HTML 位置: `module/server/web/annotator/index.html` 左侧工具栏 `<aside id="leftWindow">`
- 原始 CSS 位置: `style.css` 中 `.tool-window-left`、`.image-list`、`.image-item`、左侧 stack 相关规则
- 原始 JS 位置: `app.js`（图片上传/列表/模拟器来源）+ `layout-ui.js`（左侧布局拖拽）

## center-panel
- 原始 HTML 位置: `index.html` 中 `<section class="panel center-panel">`
- 原始 CSS 位置: `style.css` 中 `.center-panel`、`.stage-wrap`、`.roi*`、`.output*` 规则
- 原始 JS 位置: `app.js`（ROI、画布、输出面板）

## right-window
- 原始 HTML 位置: `index.html` 右侧工具栏 `<aside id="rightWindow">`
- 原始 CSS 位置: `style.css` 中 `.tool-window-right`、`.dir-selectors`、`.rule-*`、`.form-grid` 规则
- 原始 JS 位置: `app.js`（规则编辑与保存）+ `layout-ui.js`（右侧布局拖拽）
