# 全局布局与交互示例

```css
.page-shell {
  padding: 24px 32px;
}

@media (max-width: 600px) {
  .bottom-action-bar {
    width: 100%;
    left: 0;
    right: 0;
  }
}
```

- 如果 屏幕宽度 < 600px，则 底部操作栏 必须 撑满全屏（100% width），否则 保持桌面端悬浮宽度。
- 点击遮罩层关闭弹窗。
- 表单校验失败时，错误信息出现在字段下方。
