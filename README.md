# FangFang · 镂空流彩透明桌宠 ✨

一个跑在 Windows 桌面上的透明小精灵「**方方**」：**背景透明、正方形镂空**，边框是流动的彩色渐变（流彩），内部漂浮着颜文字风格的粉色线条微表情——温柔微笑、眨眼、开心、害羞，每 30 秒舒缓变化。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab.svg)](pet.py)
[![Build](https://github.com/Summery-ice/FangFang/actions/workflows/build.yml/badge.svg)](https://github.com/Summery-ice/FangFang/actions)

纯 Python + PyQt5 绘制，无任何图片资源依赖（表情与流彩环全部**运行时矢量生成**），可打包成单文件 exe。

![方方](screenshot.png)

## 特性

- 🪟 **透明置顶**无边框窗口，鼠标拖拽移动
- 🧊 **镂空流彩方框**：4 套配色（蓝粉炫彩 / 红蓝炫彩 / 彩虹 / 青绿炫彩），流动速度可调（默认静止）
- 🎭 **颜文字系表情**：眼睛=两条弧线、嘴=一条微笑弧；待机 30s 慢速渐变 + 偶尔眨眼
- 💬 **AI 聊天**：OpenAI 兼容 API，流式逐字气泡回复，保持上下文，配置持久化
- 💬 **自言自语**：可设定间隔（秒），让方方用大模型时不时冒一句软萌的话
- 🖱️ 单击开心+聊天 / 双击跳跃 / **长按害羞** / 右键菜单（含尺寸 +−、害羞一下）
- 📦 打包为单文件 exe（无控制台黑窗）

## 快速开始（源码运行）

```bash
pip install -r requirements.txt
python pet.py
```

## 打包成单文件 exe

```bat
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name FangFang ^
  --icon assets\pet.ico ^
  --add-data "assets\faces;assets\faces" ^
  --add-data "assets\shadow.png;assets" ^
  --add-data "assets\sprite_base.png;assets" pet.py
```

产物在 `dist\FangFang.exe`（约 41MB，含 PyQt5 + requests + 素材）。

## 交互操作

| 操作 | 效果 |
|---|---|
| **拖拽** | 移动位置 |
| **单击** | 开心动作 + 弹出聊天输入框（气泡架在输入框上方） |
| **双击** | 跳跃 |
| **长按（0.85s）** | 害羞（颜文字下弯眼） |
| **左键输入回车 / 发送** | 流式 AI 回复 |
| **右键 / 托盘** | 显示隐藏、害羞一下、尺寸、API 设置、退出 |

> 桌宠默认**静止不动**（无自动漫游），位置只随拖拽改变。

## 配置

右键 → **API 设置**：

- **API 地址**：OpenAI 兼容基地址，如 `https://api.deepseek.com/v1`
- **API Key / 模型名称 / 人设提示词**
- **色彩方案**：边框流彩配色
- **流彩速度**：滑动调节（0 = 静止）
- **宠物大小**：100–500 px
- **自言自语**：间隔秒数（0 = 关闭）

设置自动保存到程序同目录 `config.json`（自动生成，**不入库**，重启自动加载）。

## 目录结构

```
pet.py              主程序（窗口/矢量渲染/表情引擎/聊天/设置）
prep.py             素材预处理（重绘表情层/阴影/图标/预览）
assets/faces/       各动作表情层（PNG，可热替换）
assets/shadow.png   柔影
assets/pet.ico      图标
test_chat.py        聊天链路回归测试（内置 mock SSE 服务器）
screenshot.png      README 截图
requirements.txt    Python 依赖
```

### 重新生成素材

```bash
pip install pillow numpy scipy
python prep.py
```

### 素材热替换（无需重打包）

在 exe 同目录建 `sprites`：
- 放 `sprites/<动作>/fNN.png`（整帧含边框）→ 整体替换动画
- 或放 `sprites/faces/<动作>/fNN.png` → 仅替换表情层

## 技术亮点

- **流彩环**：`pet.py` 运行时矢量绘制——绕圆角正方形采样点、沿周长做色相 JSON[key-stops] 插值，配合全局 `flow` 相位得到匀速流光；且配色/速度完全参数化，可在配置面板实时切换。
- **表情引擎**：待机表情不是图片轮播，而是**参数化插值**——眼弦/弯度、嘴弧线数值在 4 组颜文字姿势间做 smoothstep 渐变，线条"长"出来而非闪切。
- **气泡**：回复文本用子 `QLabel` + `heightForWidth` 精确定高，杜绝文字裁剪。

## 许可

[MIT](LICENSE)