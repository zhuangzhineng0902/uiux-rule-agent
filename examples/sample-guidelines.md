# 企业管理控制台

## 基础令牌
- 主色: #0067D1
- 页面背景色: #F5F6F8
- 卡片圆角: 8px
- 卡片阴影: 0 8px 24px rgba(0,0,0,0.12)
- 正文字号: 14px
- 正文行高: 22px
- 标题字号: 24px
- 标题字重: 700
- 表单项间距: 24px

```css
:root {
  --color-primary: #0067D1;
  --color-surface: #FFFFFF;
  --font-size-body: 14px;
  --font-size-heading: 24px;
  --radius-card: 8px;
  --shadow-card: 0 8px 24px rgba(0,0,0,0.12);
}

body {
  background-color: #F5F6F8;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 14px;
  line-height: 22px;
}

.page-shell {
  padding: 20px 32px;
}

@media (max-width: 600px) {
  .page-shell {
    padding: 16px;
  }

  .bottom-action-bar {
    width: 100%;
    left: 0;
    right: 0;
  }
}

.toolbar {
  gap: 12px;
}

.button {
  height: 32px;
  border-radius: 8px;
  background-color: #0067D1;
  color: #FFFFFF;
}

.button:hover {
  background-color: #2E86DE;
}

.button:focus-visible {
  outline: 2px solid #2E86DE;
}

.button:active {
  background-color: #0052A8;
}

.button[disabled] {
  background-color: #AEAEAE;
  opacity: 0.6;
}

.input {
  height: 32px;
  border: 1px solid #C9C9C9;
  border-radius: 8px;
}

.input:focus {
  border-color: #0067D1;
  outline: 2px solid #BFD7F5;
}

.input[disabled] {
  background-color: #F3F3F3;
  color: #AEAEAE;
}

.input.error {
  border-color: #E02128;
}

.table {
  width: 100%;
}

.table:hover {
  background-color: #F8FBFF;
}

.table .row.selected {
  background-color: #EAF3FF;
}
```

## 组件规范
- 按钮默认高度: 32px
- 按钮 hover 背景色: #2E86DE
- 按钮 focus 描边: 2px solid #2E86DE
- 按钮 disabled 透明度: 0.6
- 输入框默认边框: 1px solid #C9C9C9
- 输入框 focus 边框色: #0067D1
- 输入框 error 边框色: #E02128
- 表格选中行背景色: #EAF3FF
- 工具栏按钮间距: 12px

## 全局交互
- 如果 屏幕宽度 < 600px，则 底部操作栏 必须 撑满全屏（100% width），否则 保持桌面端悬浮宽度。
- 点击遮罩层关闭弹窗。
- 表单校验失败时，错误信息出现在字段下方。
- 操作成功后，使用 Toast 提示。
- 页面加载时，显示骨架屏。
- 用户触发删除操作时，需要二次确认弹窗。
- 页面存在未保存内容时，离开页面前需要二次确认。

## 禁止项
- 禁止 在组件中硬编码与主色接近但不一致的蓝色。
- 禁止 disabled 态仍然显示可点击手型或 hover 反馈。
- 禁止 错误提示位置在同类表单中漂移。
