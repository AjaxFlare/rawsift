# 使用指南

[English](USAGE.md)

## 安装

需要 Python 3.10 或更高版本。

```bash
python -m venv .venv
source .venv/bin/activate  # Windows：.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

如果 RAW 文件没有可用的内嵌 JPEG 预览，可安装 rawpy：

```bash
python -m pip install -e ".[raw]"
```

ExifTool 和 FFmpeg 是可选的系统级后备解码器。它们位于 `PATH` 时，程序会自动调用。

## 基本命令

```bash
raw-photo-culler 输入路径 --output 输出目录 [选项]
```

输入路径可以是单个支持的文件，也可以是文件夹。文件夹会递归扫描。如果指定的输出目录已经包含文件，程序会建立带编号的新目录，不会覆盖旧报告。

## 参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--profile general\|macro-nature` | `general` | 选择技术评分权重。 |
| `--keep-rate 0.10..0.80` | `0.25` | 非包围组候选中标为精选的比例。 |
| `--duplicate-window 1..100` | `8` | 每张照片向前比较的相邻文件数量。 |
| `--duplicate-similarity 0.80..0.99` | `0.90` | 普通重复片的感知相似度阈值。 |
| `--max-preview 800..4000` | `1600` | 预览图最长边像素。 |
| `--bracket-detection auto\|off` | `auto` | 开启或关闭曝光/对焦包围识别。 |
| `--copy-bracket-originals` | 关闭 | 将识别出的包围组完整原片复制到报告子目录。 |
| `--export-xmp` | 关闭 | 在报告目录下生成 Lightroom 兼容的 XMP 星级文件。 |

## 评分模式

### General

主要使用全画面清晰度，适合旅行、活动、人像、风光和混合照片文件夹。

### Macro nature

提高画面中心 60% 区域的清晰度权重，适合昆虫、花卉、小动物和自然近摄。它仍是技术指标，必须人工确认昆虫眼部或目标身体细节是否真正合焦。

## 使用示例

普通选片：

```bash
raw-photo-culler ~/Pictures/Trip --output ./trip-report
```

昆虫与微距：

```bash
raw-photo-culler ~/Pictures/Insects \
  --output ./insect-report \
  --profile macro-nature \
  --keep-rate 0.30
```

较长的鸟类连拍：

```bash
raw-photo-culler ~/Pictures/Birds \
  --output ./bird-report \
  --duplicate-window 20
```

生成 XMP 建议，但不写入原片所在目录：

```bash
raw-photo-culler ~/Pictures/RAW \
  --output ./review \
  --export-xmp
```

明确接受额外存储占用后，复制包围组完整原片：

```bash
raw-photo-culler ~/Pictures/HDR-and-Stacks \
  --output ./review \
  --copy-bracket-originals
```

## 推荐复核顺序

1. 查看 `summary.json`，核对发现、成功分析、失败和包围组数量。
2. 打开 `report.html`。
3. 优先检查曝光包围组和对焦包围组。
4. 人工确认所有中置信度包围组。
5. 对每个普通重复组至少比较评分最高的两张。
6. 将 `reject` 视为待复核对象，不要直接执行删除。

## 标签含义

| 标签 | 含义 |
|---|---|
| `pick` | 非包围照片中的强候选。 |
| `maybe` | 技术上可用，需要人工判断。 |
| `duplicate` | 普通近重复组中排名较低的照片。 |
| `exposure-bracket` | HDR 或曝光合成序列的完整成员。 |
| `focus-bracket` | 景深合成序列的完整成员。 |
| `reject` | 可能存在技术问题，仍需人工确认。 |

## 原片安全

正常工作流只在输出目录写入文件，源文件以只读方式打开。程序不会删除、移动、重命名、覆盖或修改源文件。`--copy-bracket-originals` 只执行复制，不会移除原文件。

