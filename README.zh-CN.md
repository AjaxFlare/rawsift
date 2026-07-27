# rawsift

**Bracket-aware, non-destructive RAW photo culling.**

[English](README.md) | 简体中文

[![Tests](https://github.com/AjaxFlare/rawsift/actions/workflows/tests.yml/badge.svg)](https://github.com/AjaxFlare/rawsift/actions/workflows/tests.yml)
[![最新版本](https://img.shields.io/github/v/release/AjaxFlare/rawsift)](https://github.com/AjaxFlare/rawsift/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

rawsift 是一款非破坏式 RAW 照片智能初筛工具，可识别曝光包围和对焦包围序列、归组连拍照片、评估技术质量，并生成可人工复核的 HTML 报告，全程不修改原始照片。

适用于 RAW、连拍、HDR 包围、微距景深合成、昆虫、自然、旅行和活动摄影。

## 主要功能

- 支持 NEF、NRW、DNG、CR2、CR3、ARW、RAF、ORF、RW2、PEF、SRW、JPEG、TIFF、PNG 和 WebP。
- 根据 EXIF 曝光参数或稳定构图下的亮度阶梯识别曝光包围。
- 根据相机元数据、对焦距离变化或清晰平面迁移识别对焦包围。
- 包围序列优先于重复筛选，组内所有照片都会被保留。
- 使用感知哈希和颜色相似度识别普通重复连拍。
- 在同一批次内计算清晰度、中心清晰度、曝光、剪切和对比度评分。
- 提供 `general` 和 `macro-nature` 两种评分模式。
- 输出 HTML、CSV、JSON、联系表、独立包围组预览，以及可选的 Lightroom XMP 星级文件。
- 不删除、不移动、不重命名、不覆盖、不修改任何原片。

## Windows 程序下载

**[下载 rawsift 0.2.0 Windows x64 版](https://github.com/AjaxFlare/rawsift/releases/download/v0.2.0/rawsift-0.2.0-windows-x64.exe)**

该便携式程序已包含 Python 和应用所需依赖：

1. 下载并双击 `rawsift-0.2.0-windows-x64.exe`。
2. 使用 rawsift 时请保持控制台窗口开启。
3. 软件会在默认浏览器中打开 `http://127.0.0.1:8765`。
4. 关闭控制台窗口即可停止本地软件。

无需安装，也不要求电脑已有 Python 环境。任务数据保存在 `%USERPROFILE%\.rawsift\jobs`。目前 EXE 尚未进行代码签名，因此 Windows SmartScreen 可能显示“未知发布者”提示；Release 页面提供 SHA-256 校验值和测试信息。

其他版本和更新说明请查看 [GitHub Releases](https://github.com/AjaxFlare/rawsift/releases)。

## 从源码安装 / CLI 快速开始

```bash
git clone https://github.com/AjaxFlare/rawsift.git
cd rawsift
python -m venv .venv
source .venv/bin/activate  # Windows：.venv\Scripts\activate
python -m pip install -e .

rawsift /path/to/photos \
  --output ./rawsift-report \
  --profile macro-nature
```

运行完成后打开 `rawsift-report/report.html`。

## 本地软件与外接视觉 API

rawsift 现在包含适用于 Windows 和 macOS 的本地浏览器软件。确定性技术初筛、RAW 解码、包围识别和报告生成都在电脑本机完成。可选的 OpenAI 兼容视觉 API 只负责判断构图、主体清晰度、表情、时机和干扰元素。

Windows 用户可以直接运行上面的便携版程序。macOS、开发环境或希望从源码安装的用户可以使用：

```bash
python -m pip install -e ".[app,raw]"
rawsift-app
```

软件会自动打开 `http://127.0.0.1:8765`。在界面的「API 设置」中填写服务地址、模型和 API Key。也可以使用环境变量：

```bash
export OPENAI_API_KEY="你的密钥"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export RAWSIFT_VISION_MODEL="gpt-5.6"
rawsift-app
```

服务仅监听本机地址。API Key 不会写入任务文件或日志。每次 AI 复核最多发送 8 张经过尺寸和质量限制的 JPEG 预览，RAW 原片不会发送给 API。

## 作为 ChatGPT/Codex Skill 使用

将完整仓库克隆或复制到个人 Skill 环境。仓库根目录已经包含所需文件：

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/cull_photos.py`
- `references/scoring.md`

调用示例：

> Use $rawsift to cull this RAW folder in macro-nature mode. Keep about 25%, and group exposure and focus brackets separately.

## 包围序列处理

包围识别先于普通重复片识别。

| 序列类型 | 主要判断依据 | 输出位置 | 筛选行为 |
|---|---|---|---|
| 曝光包围 | EXIF/AEB 信息；缺失时使用构图稳定且亮度呈阶梯变化 | `bracket-groups/exposure/E001/` | 完整保留序列 |
| 对焦包围 | 对焦位移元数据或对焦距离；缺失时检测稳定曝光下的清晰区域迁移 | `bracket-groups/focus/F001/` | 完整保留序列 |
| 普通连拍 | 感知哈希与颜色相似度 | 重复组 `G001` | 推荐技术质量最强的一张 |

依靠画面推断的包围组会标注识别置信度。中置信度组必须人工复核。

## 输出结构

```text
rawsift-report/
├── report.html
├── summary.json
├── analysis.json
├── analysis.csv
├── previews/
├── contact-sheets/
├── bracket-groups/
│   ├── exposure/E001/
│   └── focus/F001/
└── xmp-sidecars/          # 仅在使用 --export-xmp 时生成
```

包围组目录默认保存预览副本和机器可读清单。只有明确使用 `--copy-bracket-originals` 时，才会复制完整 RAW 原片。

## 可选 RAW 解码器

Pillow 和 NumPy 为必需依赖。对于大量 RAW 文件，工具无需额外软件即可提取内嵌 JPEG 预览；存在以下组件时也会自动调用：

1. ExifTool
2. RAW 内嵌 JPEG
3. rawpy
4. FFmpeg

安装 rawpy 支持：

```bash
python -m pip install -e ".[raw]"
```

## 文档

- [本地软件与外接 API 完整指南](docs/APP.zh-CN.md)
- [Local app and external API guide](docs/APP.md)
- [完整中文使用指南](docs/USAGE.zh-CN.md)
- [中文识别与评分算法](docs/ALGORITHM.zh-CN.md)
- [English usage guide](docs/USAGE.md)
- [English algorithm guide](docs/ALGORITHM.md)

## 安全性与局限

- 所有评分仅在当前批次内有效，不应跨批次直接比较。
- 有意运动模糊、剪影、高调和低调照片可能受到误判。
- 主体运动或手持构图偏移可能表现得类似焦平面迁移。
- 确定性脚本不能判断人物表情、叙事性、昆虫眼部对焦和艺术价值，最终选片仍需视觉复核。
- 自动标签只是建议，不是删除指令。

## 许可证

[MIT](LICENSE)
