import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

type ActionItem = { task: string; owner: string | null; due: string | null };
type Structured = {
  title: string;
  summary: string;
  key_points: string[];
  action_items: ActionItem[];
};
type ParseMeta = {
  model_ocr: string;
  model_llm: string | null;
  warnings: string[];
  mock: boolean;
  truncated_chars: number | null;
};
type ParsePdfResponse = {
  markdown: string;
  structured: Structured | null;
  meta: ParseMeta;
};

type PagedPage = { page: number; char_count: number; ok: boolean; error: string | null };
type ParsePdfPagedResponse = {
  document_id: string;
  filename: string;
  page_count: number;
  pages: PagedPage[];
  meta: { model_ocr: string; mock: boolean; warnings: string[] };
};

type ChatMsg = { role: "user" | "assistant"; content: string };

type Mode = "single" | "paged";

type JobProgress = {
  status: string;
  phase?: string;
  page_current?: number;
  page_total?: number;
  message?: string;
};

export default function App() {
  const [mode, setMode] = useState<Mode>("single");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [data, setData] = useState<ParsePdfResponse | null>(null);

  const [paged, setPaged] = useState<ParsePdfPagedResponse | null>(null);
  const [jobProgress, setJobProgress] = useState<JobProgress | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatNote, setChatNote] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, chatBusy]);

  const onFileSingle = useCallback(async (file: File | null) => {
    setErr(null);
    setData(null);
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErr("请选择 .pdf 文件");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const res = await fetch("/api/parse-pdf", { method: "POST", body: fd });
      const text = await res.text();
      if (!res.ok) {
        setErr(`HTTP ${res.status}: ${text.slice(0, 800)}`);
        return;
      }
      setData(JSON.parse(text) as ParsePdfResponse);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const onFilePaged = useCallback(async (file: File | null) => {
    setErr(null);
    setPaged(null);
    setJobProgress(null);
    setChatMessages([]);
    setChatNote(null);
    esRef.current?.close();
    esRef.current = null;
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErr("请选择 .pdf 文件");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const res = await fetch("/api/documents/parse-paged-async", { method: "POST", body: fd });
      const text = await res.text();
      if (!res.ok) {
        setErr(`HTTP ${res.status}: ${text.slice(0, 800)}`);
        return;
      }
      const { events_url } = JSON.parse(text) as { job_id: string; events_url: string };
      setJobProgress({ status: "queued", message: "已排队" });

      const es = new EventSource(events_url);
      esRef.current = es;
      let finished = false;
      es.onmessage = (ev) => {
        try {
          const payload = JSON.parse(ev.data) as Record<string, unknown>;
          setJobProgress({
            status: String(payload.status ?? ""),
            phase: payload.phase != null ? String(payload.phase) : undefined,
            page_current: typeof payload.page_current === "number" ? payload.page_current : undefined,
            page_total: typeof payload.page_total === "number" ? payload.page_total : undefined,
            message: payload.message != null ? String(payload.message) : undefined,
          });
          if (payload.status === "completed" && payload.result) {
            finished = true;
            setPaged(payload.result as ParsePdfPagedResponse);
            es.close();
            if (esRef.current === es) esRef.current = null;
            setBusy(false);
          }
          if (payload.status === "failed") {
            finished = true;
            setErr(String(payload.error || "任务失败"));
            es.close();
            if (esRef.current === es) esRef.current = null;
            setBusy(false);
          }
        } catch {
          finished = true;
          setErr("SSE 数据解析失败");
          es.close();
          if (esRef.current === es) esRef.current = null;
          setBusy(false);
        }
      };
      es.onerror = () => {
        if (finished) return;
        es.close();
        if (esRef.current === es) esRef.current = null;
        setBusy(false);
        setErr("SSE 连接中断（若任务仍在后端执行，可稍后 GET /api/documents/jobs/<id> 轮询）");
      };
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }, []);

  const downloadMd = () => {
    if (!data) return;
    const blob = new Blob([data.markdown], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "ocr-result.md";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const downloadPagedExport = () => {
    if (!paged) return;
    window.open(`/api/documents/${paged.document_id}/export.md`, "_blank");
  };

  const sendChat = async () => {
    const q = chatInput.trim();
    if (!paged || !q || chatBusy) return;
    setChatInput("");
    const next: ChatMsg[] = [...chatMessages, { role: "user", content: q }];
    setChatMessages(next);
    setChatBusy(true);
    setChatNote(null);
    setErr(null);
    try {
      const res = await fetch(`/api/documents/${paged.document_id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: next.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      const text = await res.text();
      if (!res.ok) {
        setErr(`对话 HTTP ${res.status}: ${text.slice(0, 600)}`);
        return;
      }
      const body = JSON.parse(text) as { reply: string; note: string; router_pages?: number[] };
      const extra =
        body.router_pages && body.router_pages.length > 0
          ? ` 路由页: [${body.router_pages.slice(0, 12).join(",")}${body.router_pages.length > 12 ? "…" : ""}]`
          : "";
      setChatMessages((prev) => [...prev, { role: "assistant", content: body.reply }]);
      setChatNote((body.note ?? "") + extra);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setChatBusy(false);
    }
  };

  const card: React.CSSProperties = {
    padding: "1rem",
    background: "#fff",
    borderRadius: 8,
    border: "1px solid #e2e5eb",
    marginBottom: "1rem",
  };

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem" }}>
      <h1 style={{ marginTop: 0 }}>PDF → OCR → Qwen</h1>
      <p style={{ color: "#444" }}>
        开发模式下通过 Vite 代理访问后端 <code>/api/*</code>（默认 <code>127.0.0.1:8765</code>）。
      </p>

      <div style={{ ...card, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600 }}>模式</span>
        <label style={{ cursor: "pointer" }}>
          <input
            type="radio"
            name="mode"
            checked={mode === "single"}
            onChange={() => {
              setMode("single");
              setErr(null);
            }}
          />{" "}
          整本 OCR + 结构化（原流程）
        </label>
        <label style={{ cursor: "pointer" }}>
          <input
            type="radio"
            name="mode"
            checked={mode === "paged"}
            onChange={() => {
              setMode("paged");
              setErr(null);
            }}
          />{" "}
          按页拆分 OCR + 存储 + 对话
        </label>
      </div>

      <section style={card}>
        <label style={{ fontWeight: 600 }}>
          {mode === "single"
            ? "选择 PDF（整本）"
            : "选择 PDF（后台按页 OCR + SSE 进度；完成后可对话）"}
        </label>
        <input
          type="file"
          accept="application/pdf,.pdf"
          disabled={busy}
          style={{ display: "block", marginTop: 8 }}
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            void (mode === "single" ? onFileSingle(f) : onFilePaged(f));
            e.target.value = "";
          }}
        />
        {mode === "single" && busy && <p>处理中…</p>}
        {mode === "paged" && busy && !jobProgress && <p>提交任务中…</p>}
        {mode === "paged" && jobProgress && (
          <div style={{ marginTop: 12 }}>
            <p style={{ margin: "0 0 8px", fontSize: 14 }}>
              <strong>任务</strong>：{jobProgress.message || jobProgress.status}
              {jobProgress.phase ? `（${jobProgress.phase}）` : ""}
            </p>
            {jobProgress.page_total != null && jobProgress.page_total > 0 ? (
              <div
                style={{
                  height: 10,
                  background: "#e8ebf0",
                  borderRadius: 6,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.min(100, Math.round((100 * (jobProgress.page_current ?? 0)) / jobProgress.page_total))}%`,
                    height: "100%",
                    background: "#2563eb",
                    transition: "width 0.25s ease-out",
                  }}
                />
              </div>
            ) : null}
            {jobProgress.page_total != null && jobProgress.page_total > 0 ? (
              <p style={{ margin: "6px 0 0", fontSize: 13, color: "#555" }}>
                页进度 {jobProgress.page_current ?? 0} / {jobProgress.page_total}
              </p>
            ) : null}
          </div>
        )}
        {err && (
          <pre
            style={{
              marginTop: 12,
              padding: 12,
              background: "#fff4f4",
              borderRadius: 6,
              overflow: "auto",
              whiteSpace: "pre-wrap",
            }}
          >
            {err}
          </pre>
        )}
      </section>

      {mode === "single" && data && (
        <>
          <section style={card}>
            <h2 style={{ marginTop: 0 }}>元信息</h2>
            <ul>
              <li>
                <code>meta.mock</code>：{String(data.meta.mock)}
              </li>
              <li>
                <code>model_ocr</code>：{data.meta.model_ocr}
              </li>
              <li>
                <code>model_llm</code>：{data.meta.model_llm ?? "null"}
              </li>
              {data.meta.truncated_chars != null && (
                <li>
                  <code>truncated_chars</code>：{data.meta.truncated_chars}
                </li>
              )}
            </ul>
            {data.meta.warnings.length > 0 && (
              <div>
                <strong>warnings</strong>
                <ul>
                  {data.meta.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section style={card}>
            <h2 style={{ marginTop: 0 }}>结构化（Qwen）</h2>
            {!data.structured ? (
              <p>
                无结构化结果（<code>structured</code> 为 null）。
              </p>
            ) : (
              <>
                <h3>{data.structured.title || "（无标题）"}</h3>
                <p>{data.structured.summary}</p>
                <h4>要点</h4>
                <ul>
                  {data.structured.key_points.map((k, i) => (
                    <li key={i}>{k}</li>
                  ))}
                </ul>
                <h4>行动项</h4>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>任务</th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>负责人</th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>期限</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.structured.action_items.map((a, i) => (
                      <tr key={i}>
                        <td style={{ padding: "6px 0", verticalAlign: "top" }}>{a.task}</td>
                        <td style={{ padding: "6px 0" }}>{a.owner ?? ""}</td>
                        <td style={{ padding: "6px 0" }}>{a.due ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </section>

          <section style={card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0 }}>Markdown（OCR）</h2>
              <button type="button" onClick={downloadMd}>
                下载 .md
              </button>
            </div>
            <div
              style={{
                marginTop: 12,
                maxHeight: 480,
                overflow: "auto",
                padding: 12,
                background: "#fafafa",
                borderRadius: 6,
              }}
            >
              <ReactMarkdown>{data.markdown}</ReactMarkdown>
            </div>
          </section>
        </>
      )}

      {mode === "paged" && paged && (
        <>
          <section style={card}>
            <h2 style={{ marginTop: 0 }}>多页解析结果</h2>
            <p>
              <strong>document_id</strong>：<code>{paged.document_id}</code>
            </p>
            <p>
              文件：<code>{paged.filename}</code>，共 <strong>{paged.page_count}</strong> 页；每页 Markdown 已写入服务端{" "}
              <code>data/documents/&lt;id&gt;/page_XXXX.md</code>（见 <code>/health</code> 中 <code>documents_storage</code>
              ）。
            </p>
            <p>
              <code>model_ocr</code>：{paged.meta.model_ocr}，<code>mock</code>：{String(paged.meta.mock)}
            </p>
            <button type="button" onClick={downloadPagedExport} style={{ marginRight: 8 }}>
              下载合并全部页 .md
            </button>
            {paged.meta.warnings.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong>warnings</strong>
                <ul>
                  {paged.meta.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
            <h3>各页状态</h3>
            <ul style={{ fontSize: 14 }}>
              {paged.pages.map((p) => (
                <li key={p.page}>
                  第 {p.page} 页 — {p.ok ? "成功" : "失败"}，{p.char_count} 字符
                  {p.error ? `（${p.error}）` : ""}
                  {" · "}
                  <a href={`/api/documents/${paged.document_id}/pages/${p.page}/markdown`} target="_blank" rel="noreferrer">
                    查看 JSON
                  </a>
                </li>
              ))}
            </ul>
          </section>

          <section style={card}>
            <h2 style={{ marginTop: 0 }}>文档对话</h2>
            <p style={{ color: "#555", fontSize: 14 }}>
              根据已 OCR 的页面内容回答问题。会先由<strong>大模型阅读每页短摘录</strong>标出相关页码，再拼全文摘录送入对话；路由失败时回退为关键词选页。总字数仍受上限约束，极端情况下可能截断。
            </p>
            <div
              style={{
                border: "1px solid #e2e5eb",
                borderRadius: 8,
                padding: 12,
                maxHeight: 320,
                overflow: "auto",
                background: "#fafafa",
                marginBottom: 12,
              }}
            >
              {chatMessages.length === 0 && <p style={{ color: "#888", margin: 0 }}>发送第一条消息开始对话。</p>}
              {chatMessages.map((m, i) => (
                <div
                  key={i}
                  style={{
                    marginBottom: 12,
                    textAlign: m.role === "user" ? "right" : "left",
                  }}
                >
                  <div
                    style={{
                      display: "inline-block",
                      maxWidth: "85%",
                      padding: "8px 12px",
                      borderRadius: 8,
                      background: m.role === "user" ? "#dbeafe" : "#fff",
                      border: "1px solid #e2e5eb",
                      textAlign: "left",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    <strong>{m.role === "user" ? "你" : "助手"}</strong>
                    <div style={{ marginTop: 4 }}>{m.content}</div>
                  </div>
                </div>
              ))}
              {chatBusy && <p style={{ color: "#666" }}>思考中…</p>}
              <div ref={chatEndRef} />
            </div>
            {chatNote && (
              <p style={{ fontSize: 13, color: "#555" }}>
                <strong>说明</strong>：{chatNote}
              </p>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                style={{ flex: 1, padding: "8px 10px", borderRadius: 6, border: "1px solid #ccc" }}
                placeholder="例如：第三页的合同金额是多少？"
                value={chatInput}
                disabled={chatBusy}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void sendChat();
                  }
                }}
              />
              <button type="button" disabled={chatBusy || !chatInput.trim()} onClick={() => void sendChat()}>
                发送
              </button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
