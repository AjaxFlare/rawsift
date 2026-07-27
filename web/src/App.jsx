import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Aperture, BrainCircuit, Check, ChevronDown, CircleAlert, CloudUpload, Download,
  Eye, FileArchive, FileImage, FolderOpen, Gauge, Image, Info, KeyRound, Layers3,
  LoaderCircle, Menu, PanelRightClose, PanelRightOpen, RefreshCw, Search, Settings,
  ShieldCheck, SlidersHorizontal, Sparkles, Star, TestTube2, X, Zap,
} from "lucide-react";
import { api } from "./api";

const FILTERS = [
  ["all", "全部"], ["pick", "精选"], ["maybe", "备选"],
  ["exposure-bracket", "曝光包围"], ["focus-bracket", "对焦包围"],
  ["duplicate", "重复"], ["reject", "技术问题"],
];

const LABELS = {
  pick: "精选", maybe: "备选", duplicate: "重复", reject: "技术问题",
  "exposure-bracket": "曝光包围", "focus-bracket": "对焦包围",
};

const DEFAULT_PROVIDER = {
  base_url: "https://api.openai.com/v1",
  model: "gpt-5.6",
  api_key: "",
  api_mode: "responses",
};

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function fileName(path = "") {
  return path.split(/[\\/]/).pop();
}

function scoreTone(value = 0) {
  if (value >= 75) return "good";
  if (value >= 45) return "warn";
  return "bad";
}

function Stat({ value, label, accent }) {
  return <div className={`stat ${accent || ""}`}><strong>{value ?? 0}</strong><span>{label}</span></div>;
}

function Sidebar({ view, setView, openSettings, mobileOpen, setMobileOpen }) {
  const nav = [
    ["library", FolderOpen, "本地初筛"],
    ["review", BrainCircuit, "AI 复核"],
    ["exports", Download, "导出结果"],
  ];
  return <aside className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}>
    <button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="关闭菜单"><X /></button>
    <div className="wordmark"><span className="brand-mark" />raw<span>sift</span></div>
    <div className="eyebrow">RAW PHOTO WORKSPACE</div>
    <nav>
      {nav.map(([id, Icon, label]) => <button key={id} className={view === id ? "active" : ""} onClick={() => { setView(id); setMobileOpen(false); }}><Icon />{label}</button>)}
    </nav>
    <div className="sidebar-bottom">
      <div className="privacy-mini"><ShieldCheck /><div><b>原片留在本机</b><span>仅压缩预览可发送给 API</span></div></div>
      <button className="settings-link" onClick={openSettings}><Settings />API 设置</button>
      <div className="version">rawsift 0.2.0</div>
    </div>
  </aside>;
}

function ImportPanel({ busy, onFiles }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const accept = ".nef,.nrw,.dng,.cr2,.cr3,.arw,.raf,.orf,.rw2,.pef,.srw,.jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp";
  const choose = () => input.current?.click();
  const dropped = (event) => {
    event.preventDefault();
    setDragging(false);
    onFiles(Array.from(event.dataTransfer.files));
  };
  return <section className={`import-panel ${dragging ? "dragging" : ""}`} onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={dropped}>
    <input ref={input} type="file" accept={accept} multiple webkitdirectory="" directory="" hidden onChange={(e) => onFiles(Array.from(e.target.files))} />
    <div className="upload-icon"><CloudUpload /></div>
    <div><h2>{busy ? "正在导入并分析…" : "拖入照片文件夹，开始本地初筛"}</h2><p>支持主流相机 RAW 与普通图片 · 不移动、不覆盖、不删除原片</p></div>
    <button className="primary outline" disabled={busy} onClick={choose}>{busy ? <LoaderCircle className="spin" /> : <FolderOpen />}选择文件夹</button>
  </section>;
}

function JobStrip({ jobs, current, selectJob, refresh, loading }) {
  if (!jobs.length) return null;
  return <section className="job-strip">
    <div className="job-state"><span className={`status-dot ${current?.status || ""}`} />
      <div><b>{current?.name}</b><span>{current?.file_count || 0} 张 · {current?.status === "completed" ? "分析完成" : current?.status === "failed" ? "分析失败" : "处理中"} · {formatDate(current?.created_at)}</span></div>
    </div>
    <div className="job-actions">
      <label className="select-wrap"><select value={current?.id || ""} onChange={(e) => selectJob(e.target.value)}>{jobs.map((job) => <option value={job.id} key={job.id}>{job.name}</option>)}</select><ChevronDown /></label>
      <button className="icon-button" onClick={refresh} aria-label="刷新"><RefreshCw className={loading ? "spin" : ""} /></button>
      {current?.status === "completed" && <a className="secondary" href={`/api/jobs/${current.id}/files/report.html`} target="_blank" rel="noreferrer"><Eye />完整报告</a>}
    </div>
  </section>;
}

function FilterBar({ filter, setFilter, counts, search, setSearch }) {
  return <div className="filterbar">
    <div className="filters">{FILTERS.map(([id, label]) => <button key={id} className={filter === id ? "active" : ""} onClick={() => setFilter(id)}>{label}<span>{id === "all" ? Object.values(counts).reduce((a, b) => a + b, 0) : counts[id] || 0}</span></button>)}</div>
    <label className="search"><Search /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索文件名" /></label>
  </div>;
}

function PhotoCard({ item, jobId, selected, checked, onSelect, onCheck }) {
  return <article className={`photo-card ${selected ? "selected" : ""}`} onClick={onSelect}>
    <div className="photo-frame">
      <img src={`/api/jobs/${jobId}/files/${item.preview}`} alt={fileName(item.source)} loading="lazy" />
      <button className={`check ${checked ? "checked" : ""}`} onClick={(e) => { e.stopPropagation(); onCheck(); }} aria-label="选择照片">{checked && <Check />}</button>
      {item.bracket_group && <span className="group-chip"><Layers3 />{item.bracket_group} · {item.bracket_order}/{item.bracket_count}</span>}
      {item.duplicate_group && <span className="group-chip"><FileArchive />{item.duplicate_group}</span>}
    </div>
    <div className="photo-meta">
      <div><b title={item.source}>{fileName(item.source)}</b><span>{item.bracket_type === "exposure" ? `${item.exposure_compensation ?? "—"} EV` : item.bracket_type === "focus" ? `焦点 ${item.bracket_order}` : LABELS[item.label]}</span></div>
      <strong className={scoreTone(item.technical_score)}>{Math.round(item.technical_score)}</strong>
    </div>
  </article>;
}

function EmptyWorkspace({ failed }) {
  return <div className="empty-workspace"><div className="empty-art"><Image /><span><Sparkles /></span></div><h2>{failed ? "这批照片未能完成分析" : "选择一个照片文件夹"}</h2><p>{failed || "rawsift 会先识别曝光包围、对焦包围和连拍，再给出保守的技术初筛建议。"}</p></div>;
}

function Inspector({ item, jobId, providerReady, openSettings, onClose }) {
  if (!item) return <aside className="inspector placeholder"><PanelRightClose /><h3>照片详情</h3><p>点选照片后查看技术指标与分组依据。</p></aside>;
  const metrics = [
    ["清晰度", item.focus_score], ["中心清晰", item.center_focus_score],
    ["曝光", item.exposure_score], ["对比度", item.contrast_score],
  ];
  return <aside className="inspector">
    <div className="inspector-head"><div><span>所选照片</span><b>{fileName(item.source)}</b></div><button className="icon-button inspector-close" onClick={onClose}><X /></button></div>
    <img className="inspector-image" src={`/api/jobs/${jobId}/files/${item.preview}`} alt="" />
    <div className="verdict"><span className={`label ${item.label}`}>{LABELS[item.label]}</span><strong className={scoreTone(item.technical_score)}>{Math.round(item.technical_score)}</strong></div>
    <p className="reason">{item.reason}</p>
    <div className="metric-list">{metrics.map(([name, value]) => <div className="metric" key={name}><div><span>{name}</span><b>{Math.round(value || 0)}</b></div><i><em style={{ width: `${Math.max(2, value || 0)}%` }} /></i></div>)}</div>
    <div className="detail-grid">
      <div><span>快门</span><b>{item.exposure_time || "—"}</b></div><div><span>光圈</span><b>{item.f_number ? `f/${item.f_number}` : "—"}</b></div>
      <div><span>ISO</span><b>{item.iso || "—"}</b></div><div><span>尺寸</span><b>{item.width} × {item.height}</b></div>
      <div><span>解码器</span><b>{item.decoder}</b></div><div><span>分组</span><b>{item.bracket_group || item.duplicate_group || "单张"}</b></div>
    </div>
    <button className="provider-status" onClick={openSettings}><span className={providerReady ? "online" : ""} /><BrainCircuit />{providerReady ? "视觉 API 已配置" : "配置视觉 API"}<ChevronDown /></button>
  </aside>;
}

function ProviderModal({ open, close, provider, setProvider, testState, onTest }) {
  if (!open) return null;
  const field = (key, value) => setProvider((old) => ({ ...old, [key]: value }));
  return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}>
    <section className="modal">
      <div className="modal-head"><div><span className="modal-icon"><BrainCircuit /></span><div><h2>视觉 API 设置</h2><p>使用兼容 OpenAI 协议的外接服务</p></div></div><button className="icon-button" onClick={close}><X /></button></div>
      <div className="security-note"><ShieldCheck /><p><b>本机优先</b><span>API 密钥只保存在当前浏览器会话。复核时最多上传 8 张经过压缩的 JPEG 预览，不上传 RAW 原片。</span></p></div>
      <label>API 地址<input value={provider.base_url} onChange={(e) => field("base_url", e.target.value)} placeholder="https://api.openai.com/v1" /></label>
      <div className="field-row"><label>模型<input value={provider.model} onChange={(e) => field("model", e.target.value)} placeholder="gpt-5.6" /></label><label>API 模式<select value={provider.api_mode} onChange={(e) => field("api_mode", e.target.value)}><option value="responses">Responses API</option><option value="chat-completions">Chat Completions</option></select></label></div>
      <label>API Key<div className="key-field"><KeyRound /><input type="password" value={provider.api_key} onChange={(e) => field("api_key", e.target.value)} autoComplete="off" placeholder="sk-…" /></div></label>
      {testState.message && <div className={`test-result ${testState.ok ? "success" : "error"}`}>{testState.ok ? <Check /> : <CircleAlert />}{testState.message}</div>}
      <div className="modal-actions"><button className="secondary" onClick={close}>取消</button><button className="primary" disabled={testState.loading} onClick={onTest}>{testState.loading ? <LoaderCircle className="spin" /> : <TestTube2 />}测试并保存</button></div>
    </section>
  </div>;
}

function AiReview({ analysis, jobId, checked, setChecked, provider, providerReady, openSettings, setToast }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const selectedItems = analysis?.items?.filter((item) => checked.has(item.source)) || [];
  const run = async () => {
    if (!providerReady) return openSettings();
    if (!selectedItems.length) return setToast({ type: "error", text: "请先选择 1–8 张照片" });
    setLoading(true);
    try {
      const data = await api.review(jobId, { ...provider, sources: selectedItems.slice(0, 8).map((item) => item.source) });
      setResult(data);
      setToast({ type: "success", text: "视觉复核完成" });
    } catch (error) { setToast({ type: "error", text: error.message }); }
    finally { setLoading(false); }
  };
  if (!analysis) return <EmptyWorkspace />;
  return <div className="ai-page">
    <section className="ai-hero"><div><span className="overline"><Sparkles />OPTIONAL VISION REVIEW</span><h1>在技术初筛之后，补充视觉判断</h1><p>选择最多 8 张压缩预览，让外接视觉 API 判断主体、构图、时机和干扰元素。包围组仍保持完整。</p></div><button className="primary" disabled={loading} onClick={run}>{loading ? <LoaderCircle className="spin" /> : <Zap />}复核所选 {Math.min(checked.size, 8)} 张</button></section>
    <div className="ai-layout"><section className="review-picker"><div className="section-title"><div><h2>选择预览</h2><p>当前已选 {checked.size} 张，单次最多发送 8 张</p></div><button className="text-button" onClick={() => setChecked(new Set())}>清空</button></div><div className="compact-grid">{analysis.items.slice(0, 40).map((item) => <button key={item.source} className={checked.has(item.source) ? "chosen" : ""} onClick={() => setChecked((old) => { const next = new Set(old); next.has(item.source) ? next.delete(item.source) : next.size < 8 && next.add(item.source); return next; })}><img src={`/api/jobs/${jobId}/files/${item.preview}`} alt="" /><span>{checked.has(item.source) && <Check />}</span><b>{fileName(item.source)}</b></button>)}</div></section>
      <section className="review-result"><div className="section-title"><div><h2>复核结果</h2><p>{providerReady ? `${provider.model} · 已配置` : "等待配置 API"}</p></div><button className="icon-button" onClick={openSettings}><Settings /></button></div>{result ? <><p className="ai-summary">{result.summary}</p><div className="ai-cards">{result.photos?.map((photo) => <article key={photo.filename}><div><b>{photo.filename}</b><span>{photo.recommendation}</span></div><strong>{photo.visual_score}</strong><p>{photo.notes}</p></article>)}</div></> : <div className="result-empty"><BrainCircuit /><h3>等待视觉复核</h3><p>复核结果会保存在当前批次的 <code>ai-review.json</code>。</p></div>}</section></div>
  </div>;
}

function ExportPage({ job }) {
  if (!job || job.status !== "completed") return <EmptyWorkspace />;
  const files = [["report.html", "可交互 HTML 报告", Eye], ["analysis.csv", "表格数据", FileArchive], ["analysis.json", "完整分析 JSON", FileImage], ["summary.json", "批次摘要", Gauge]];
  return <div className="export-page"><div className="page-heading"><span className="overline"><Download />EXPORT</span><h1>导出本次初筛结果</h1><p>所有结果都在本机任务目录中生成，原片没有被修改。</p></div><div className="export-grid">{files.map(([path, desc, Icon]) => <a href={`/api/jobs/${job.id}/files/${path}`} target="_blank" rel="noreferrer" key={path}><span><Icon /></span><div><b>{path}</b><p>{desc}</p></div><Download /></a>)}</div><div className="export-note"><Info /><p><b>包围组可单独检查</b><span>报告内包含曝光包围与对焦包围的独立分组，建议在删除任何照片前人工检查完整序列。</span></p></div></div>;
}

export default function App() {
  const [view, setView] = useState("library");
  const [jobs, setJobs] = useState([]);
  const [currentId, setCurrentId] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [checked, setChecked] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(() => window.innerWidth > 900);
  const [provider, setProvider] = useState(() => {
    try { return { ...DEFAULT_PROVIDER, ...JSON.parse(sessionStorage.getItem("rawsift-provider") || "{}") }; }
    catch { return DEFAULT_PROVIDER; }
  });
  const [providerReady, setProviderReady] = useState(false);
  const [testState, setTestState] = useState({ loading: false, ok: false, message: "" });
  const [toast, setToast] = useState(null);

  const current = jobs.find((job) => job.id === currentId) || jobs[0];
  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const data = await api.jobs();
      setJobs(data);
      setCurrentId((id) => id || data[0]?.id || "");
    } catch (error) { setToast({ type: "error", text: error.message }); }
    finally { if (!quiet) setLoading(false); }
  }, []);

  useEffect(() => { refresh(); api.settings().then((env) => { setProvider((old) => ({ ...old, base_url: old.base_url || env.base_url, model: old.model || env.model, api_mode: old.api_mode || env.api_mode })); setProviderReady(env.api_key_configured || Boolean(sessionStorage.getItem("rawsift-provider-ok"))); }).catch(() => {}); }, [refresh]);
  useEffect(() => {
    if (!current) return;
    if (current.status === "completed") api.analysis(current.id).then((data) => { setAnalysis(data); setSelected((old) => old && data.items.find((item) => item.source === old.source) || data.items[0] || null); }).catch((error) => setToast({ type: "error", text: error.message }));
    else setAnalysis(null);
  }, [current?.id, current?.status]);
  useEffect(() => {
    if (!current || !["queued", "running", "uploading"].includes(current.status)) return;
    const timer = setInterval(() => refresh(true), 1500);
    return () => clearInterval(timer);
  }, [current?.id, current?.status, refresh]);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(null), 4200); return () => clearTimeout(timer); }, [toast]);

  const upload = async (files) => {
    if (!files.length) return;
    setLoading(true);
    const form = new FormData();
    const firstPath = files[0].webkitRelativePath || files[0].name;
    const batchName = firstPath.includes("/") ? firstPath.split("/")[0] : "新批次";
    form.append("name", batchName);
    form.append("profile", "general");
    form.append("keep_rate", "0.25");
    files.forEach((file) => { form.append("files", file, file.name); form.append("paths", file.webkitRelativePath || file.name); });
    try {
      const job = await api.createJob(form);
      setCurrentId(job.id); setAnalysis(null); setSelected(null); setChecked(new Set());
      await refresh(true);
      setToast({ type: "success", text: `已导入 ${files.length} 个文件，正在本机分析` });
    } catch (error) { setToast({ type: "error", text: error.message }); }
    finally { setLoading(false); }
  };

  const counts = analysis?.summary?.counts || {};
  const visible = useMemo(() => (analysis?.items || []).filter((item) => (filter === "all" || item.label === filter) && (!search || item.source.toLowerCase().includes(search.toLowerCase()))), [analysis, filter, search]);
  const toggleCheck = (source) => setChecked((old) => { const next = new Set(old); next.has(source) ? next.delete(source) : next.add(source); return next; });
  const testProvider = async () => {
    setTestState({ loading: true, ok: false, message: "" });
    try {
      const result = await api.testProvider(provider);
      if (!result.ok) throw new Error(`服务返回：${result.response}`);
      sessionStorage.setItem("rawsift-provider", JSON.stringify(provider)); sessionStorage.setItem("rawsift-provider-ok", "1");
      setProviderReady(true); setTestState({ loading: false, ok: true, message: "连接成功，设置已保存到当前会话" });
    } catch (error) { setProviderReady(false); setTestState({ loading: false, ok: false, message: error.message }); }
  };

  return <div className="app-shell">
    <Sidebar {...{ view, setView, mobileOpen, setMobileOpen }} openSettings={() => setSettingsOpen(true)} />
    <main className={`workspace ${inspectorOpen && view === "library" ? "with-inspector" : ""}`}>
      <header className="topbar"><button className="icon-button menu-button" onClick={() => setMobileOpen(true)}><Menu /></button><div><span className="mobile-brand">rawsift</span><p>{view === "library" ? "非破坏式 RAW 初筛" : view === "review" ? "外接视觉 API" : "批次结果"}</p></div><div className="top-actions"><span className="local-badge"><ShieldCheck />LOCAL ONLY</span>{view === "library" && <button className="icon-button" onClick={() => setInspectorOpen((open) => !open)}>{inspectorOpen ? <PanelRightClose /> : <PanelRightOpen />}</button>}</div></header>
      {view === "library" && <>
        <div className="content"><ImportPanel busy={loading} onFiles={upload} /><JobStrip jobs={jobs} current={current} selectJob={setCurrentId} refresh={() => refresh()} loading={loading} />
          {analysis && <><div className="stats"><Stat value={analysis.summary.analyzed} label="已分析" /><Stat value={counts.pick} label="精选" accent="green" /><Stat value={counts["exposure-bracket"]} label="曝光包围" accent="orange" /><Stat value={counts["focus-bracket"]} label="对焦包围" accent="cyan" /><Stat value={(counts.duplicate || 0) + (counts.reject || 0)} label="需复核" accent="purple" /></div><FilterBar {...{ filter, setFilter, counts, search, setSearch }} /><div className="results-head"><div><h2>初筛结果</h2><p>{visible.length} 张照片 · 技术评分仅在当前批次内比较</p></div><button className="secondary"><SlidersHorizontal />排序：拍摄顺序</button></div><div className="photo-grid">{visible.map((item) => <PhotoCard key={item.source} item={item} jobId={current.id} selected={selected?.source === item.source} checked={checked.has(item.source)} onSelect={() => { setSelected(item); setInspectorOpen(true); }} onCheck={() => toggleCheck(item.source)} />)}</div></>}
          {!analysis && <EmptyWorkspace failed={current?.status === "failed" ? current.error : null} />}
        </div>
        {inspectorOpen && <Inspector item={selected} jobId={current?.id} providerReady={providerReady} openSettings={() => setSettingsOpen(true)} onClose={() => setInspectorOpen(false)} />}
      </>}
      {view === "review" && <div className="content full"><AiReview {...{ analysis, checked, setChecked, provider, providerReady, setToast }} jobId={current?.id} openSettings={() => setSettingsOpen(true)} /></div>}
      {view === "exports" && <div className="content full"><ExportPage job={current} /></div>}
    </main>
    <ProviderModal open={settingsOpen} close={() => setSettingsOpen(false)} {...{ provider, setProvider, testState }} onTest={testProvider} />
    {mobileOpen && <div className="mobile-scrim" onClick={() => setMobileOpen(false)} />}
    {toast && <div className={`toast ${toast.type}`}>{toast.type === "success" ? <Check /> : <CircleAlert />}{toast.text}</div>}
  </div>;
}
