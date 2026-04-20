# 按钮组件示例

```css
.button {
  height: 32px;
  border-radius: 8px;
  background-color: #1677FF;
  color: #FFFFFF;
}

.button:hover {
  background-color: #4096FF;
}

.button:focus-visible {
  outline: 2px solid #91C3FF;
}

.button:active {
  background-color: #0958D9;
}

.button[disabled] {
  opacity: 0.5;
  background-color: #D9D9D9;
}
```

- 按钮默认高度: 32px
- 按钮 hover 背景色: #4096FF
- 按钮 focus 描边: 2px solid #91C3FF
- 按钮 disabled 透明度: 0.5
