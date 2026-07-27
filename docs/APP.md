# rawsift local app and external API

English | [简体中文](APP.zh-CN.md)

rawsift 0.2 includes a local photo-culling application. The browser handles import, review, filtering, and optional vision requests. The Python service extracts RAW previews, computes technical scores, identifies exposure/focus brackets and bursts, and generates reports.

## Data flow

1. Select a photo directory in the browser.
2. The files are copied to `~/.rawsift/jobs/<job ID>/input/` on the same computer; the sources remain unchanged.
3. rawsift generates bounded previews, scores, groups, and reports locally.
4. Only after you explicitly start an AI review are up to eight compressed JPEG previews sent to the configured vision API.
5. The provider response is saved as `ai-review.json` in that job's report.

## Install

Python 3.10–3.12 and a current browser are required.

```bash
git clone https://github.com/AjaxFlare/rawsift.git
cd rawsift
python -m venv .venv
```

macOS / Linux:

```bash
source .venv/bin/activate
python -m pip install -e ".[app,raw]"
rawsift-app
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[app,raw]"
rawsift-app
```

The `raw` extra improves RAW compatibility. rawsift also uses ExifTool and FFmpeg as optional fallback decoders when installed.

## Launch options

```bash
rawsift-app --port 8765
rawsift-app --no-browser
```

For API-key safety, the launcher accepts only `127.0.0.1`, `localhost`, or `::1`. It is not designed to be exposed as a public service.

## Configure a vision provider

Open **API Settings** and enter:

- **API address:** the root of an OpenAI-compatible API. Public endpoints must use HTTPS; loopback development services may use plain HTTP.
- **Model:** a model that supports image input.
- **API Key:** stored only in the current browser tab's `sessionStorage` and cleared when that tab closes.
- **API mode:** prefer Responses API; choose Chat Completions for providers that expose only that interface.

Environment variables are also supported:

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | empty | Provider credential |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL |
| `RAWSIFT_VISION_MODEL` | `gpt-5.6` | Vision-capable model name |
| `RAWSIFT_API_MODE` | `responses` | `responses` or `chat-completions` |
| `RAWSIFT_DATA_DIR` | `~/.rawsift/jobs` | Local job-data directory |

Use an environment variable or the UI for credentials. Never commit a key to Git or include one in screenshots.

## Workflow

1. Choose a RAW/JPEG directory under **Local culling**.
2. Wait for the job to reach **Completed**.
3. Filter picks, maybes, exposure brackets, focus brackets, duplicates, and technical concerns.
4. Select a photo to inspect technical metrics, EXIF data, and grouping evidence.
5. Check photos that need semantic judgment and open **AI review**.
6. Run the optional review and combine it with the deterministic pass for the final decision.
7. Open the HTML, CSV, or JSON output under **Export**.

## Privacy and security

- Source photos are never deleted, overwritten, moved, renamed, or sent to the vision provider.
- API previews are limited to a 1280-pixel edge and JPEG quality 82.
- One review contains at most eight previews.
- API keys are not written to job metadata, reports, or server logs.
- Upload and report paths are checked against directory traversal.
- Bracket groups remain complete; an AI suggestion cannot split a confirmed bracket sequence.

## Frontend development

The repository includes the React + Vite source. Node.js is not required for ordinary use because the built UI ships with the Python package. To change the interface:

```bash
cd web
npm install
npm run build
cd ..
rawsift-app
```

For development, run `rawsift-app --no-browser` and `cd web && npm run dev`. Vite proxies `/api` to `127.0.0.1:8765`.

## Local endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Service health |
| `GET` | `/api/settings` | Public settings without credentials |
| `POST` | `/api/settings/test` | Test the external provider |
| `GET/POST` | `/api/jobs` | List or create jobs |
| `GET` | `/api/jobs/{id}` | Read job status |
| `GET` | `/api/jobs/{id}/analysis` | Read analysis results |
| `GET` | `/api/jobs/{id}/files/{path}` | Read a report artifact |
| `POST` | `/api/jobs/{id}/vision-review` | Review selected previews |

These endpoints serve the loopback application. They have no user-authentication layer and must not be published through an internet-facing reverse proxy.

## Troubleshooting

- **Frontend not built:** run `npm install && npm run build` under `web/`, then restart.
- **RAW cannot be decoded:** install `.[raw]`, then consider ExifTool or FFmpeg.
- **Provider test fails:** verify the `/v1` address, image support, selected API mode, credential, and provider quota.
- **Port already in use:** start with `rawsift-app --port 8766`.
- **Job failed:** inspect `stderr.log` in its local job directory. Credentials are never included there.
