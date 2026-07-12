# RawSift

**Bracket-aware, non-destructive RAW photo culling.**

[English](README.md) | 简体中文

[![Tests](https://github.com/AjaxFlare/rawsift/actions/workflows/tests.yml/badge.svg)](https://github.com/AjaxFlare/rawsift/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RawSift 是一款非破坏式 RAW 照片智能初筛工具，可识别曝光包围和对焦包围序列、归组连拍照片、评估技术质量，并生成可人工复核的 HTML 报告，全程不修改原始照片。

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

## 快速开始

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

