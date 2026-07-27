# rawsift 本地软件与外接 API

[English](APP.md) | 简体中文

rawsift 0.2 提供一个本机运行的照片初筛软件。浏览器负责导入、查看、筛选和发起视觉复核；Python 服务负责 RAW 预览提取、技术评分、曝光/对焦包围识别、连拍分组和报告生成。

## 数据流程

1. 用户在浏览器中选择照片文件夹。
2. 文件被复制到本机 `~/.rawsift/jobs/<任务 ID>/input/`，原文件保持不变。
3. rawsift 在本机生成压缩预览、评分、分组和报告。
4. 只有用户主动执行「AI 复核」时，最多 8 张压缩 JPEG 预览会发送给配置的视觉 API。
5. API 结果保存为任务报告目录中的 `ai-review.json`。

## 安装

需要 Python 3.10–3.12 和较新的浏览器。

```bash
git clone https://github.com/AjaxFlare/rawsift.git
cd rawsift
python -m venv .venv
```

macOS / Linux：

```bash
source .venv/bin/activate
python -m pip install -e ".[app,raw]"
rawsift-app
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[app,raw]"
rawsift-app
```

安装 `raw` 额外依赖能提高对 RAW 文件的兼容性。ExifTool 和 FFmpeg 存在时也会自动作为备用解码器使用。

## 启动选项

```bash
rawsift-app --port 8765
rawsift-app --no-browser
```

出于密钥安全考虑，软件只允许监听 `127.0.0.1`、`localhost` 或 `::1`，不能直接作为公网服务启动。

## 配置外接视觉 API

点击左下角「API 设置」，填写：

- **API 地址**：OpenAI 兼容服务的根地址。公网服务必须使用 HTTPS；本地服务允许使用 `http://127.0.0.1` 或 `http://localhost`。
- **模型**：支持图像输入的模型名称。
- **API Key**：仅保存在当前浏览器标签页的 `sessionStorage` 中，关闭标签页后清除。
- **API 模式**：优先选择 Responses API；兼容服务只提供旧接口时选择 Chat Completions。

也可以在启动软件前设置环境变量：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 空 | API 密钥 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容 API 地址 |
| `RAWSIFT_VISION_MODEL` | `gpt-5.6` | 视觉模型名称 |
| `RAWSIFT_API_MODE` | `responses` | `responses` 或 `chat-completions` |
| `RAWSIFT_DATA_DIR` | `~/.rawsift/jobs` | 本机任务数据目录 |

请通过系统环境变量或界面输入密钥，不要把密钥写入 Git 仓库、配置文件或问题截图。

## 使用流程

1. 在「本地初筛」选择包含 RAW/JPEG 的文件夹。
2. 等待任务状态变成「分析完成」。
3. 使用标签查看精选、备选、曝光包围、对焦包围、重复和技术问题。
4. 点击照片查看清晰度、曝光、对比度、EXIF 和分组依据。
5. 勾选需要语义判断的照片，进入「AI 复核」。
6. 运行视觉复核，并结合技术评分人工决定最终选择。
7. 在「导出结果」打开 HTML、CSV 或 JSON。

## 隐私与安全

- 原片不会被删除、覆盖、移动、重命名或发送给视觉 API。
- API 复核会把预览限制在最长边 1280 像素，并编码为质量 82 的 JPEG。
- 单次复核最多 8 张预览。
- API Key 不写入任务元数据、报告或服务日志。
- 上传路径和报告路径都会检查目录穿越。
- 包围组始终作为完整序列保留；AI 建议不能拆散确认后的包围组。

## 开发前端

仓库包含 React + Vite 源码。日常使用不需要 Node.js，因为构建产物已经随 Python 包提供。修改界面时执行：

```bash
cd web
npm install
npm run build
cd ..
rawsift-app
```

开发模式可以同时运行 `rawsift-app --no-browser` 和 `cd web && npm run dev`。Vite 会把 `/api` 代理到 `127.0.0.1:8765`。

## 本机 API

软件界面调用以下本机端点：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/health` | 健康状态 |
| `GET` | `/api/settings` | 无密钥的公开配置 |
| `POST` | `/api/settings/test` | 测试外接 API |
| `GET/POST` | `/api/jobs` | 查询或创建任务 |
| `GET` | `/api/jobs/{id}` | 读取任务状态 |
| `GET` | `/api/jobs/{id}/analysis` | 读取分析结果 |
| `GET` | `/api/jobs/{id}/files/{path}` | 读取报告文件 |
| `POST` | `/api/jobs/{id}/vision-review` | 复核所选预览 |

这些端点面向本机软件，不提供用户认证，也不应通过反向代理公开到互联网。

## 故障排查

- **页面提示前端未构建**：进入 `web/` 运行 `npm install && npm run build`，然后重启。
- **RAW 无法解码**：安装 `.[raw]`，并尝试安装 ExifTool 或 FFmpeg。
- **API 测试失败**：确认地址包含 `/v1`、模型支持图像输入、API 模式与服务兼容，并检查密钥额度。
- **端口被占用**：使用 `rawsift-app --port 8766`。
- **任务失败**：查看任务目录中的 `stderr.log`；日志不会包含 API Key。
