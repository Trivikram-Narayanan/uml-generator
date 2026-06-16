import { useState, useEffect, useCallback } from "react";
import { useGenerate } from "../hooks/useGenerate";
import { apiFetch } from "../utils/api";
import DiagramPreview from "../components/DiagramPreview";
import CodePanel from "../components/CodePanel";
import ContextInspector from "../components/ContextInspector";
import FeedbackBar from "../components/FeedbackBar";
import RefineBar from "../components/RefineBar";
import VersionHistory from "../components/VersionHistory";
import TemplateGallery from "../components/TemplateGallery";
import SearchBar from "../components/SearchBar";
import ModelSelector from "../components/ModelSelector";
import "./AppPage.css";

const DIAGRAM_TYPES = [
  { value: "sequence",  label: "Sequence",  icon: "↔", color: "#4f8ef7" },
  { value: "class",     label: "Class",     icon: "⬡", color: "#a78bfa" },
  { value: "usecase",   label: "Use Case",  icon: "◎", color: "#22c55e" },
  { value: "activity",  label: "Activity",  icon: "⬬", color: "#f59e0b" },
  { value: "component", label: "Component", icon: "⬛", color: "#06b6d4" },
  { value: "state",     label: "State",     icon: "◈", color: "#f97316" },
  { value: "er",        label: "ER",        icon: "⊞", color: "#ec4899" },
];
const LANGUAGES = ["python","javascript","typescript","java","go","rust","csharp","cpp","ruby","kotlin","swift"];

export default function AppPage() {
  const { loading, refining, error, result, setResult,
          generate, refine, regenerateCode, submitFeedback } = useGenerate();

  const [description,   setDescription]   = useState("");
  const [diagramType,   setDiagramType]   = useState("sequence");
  const [language,      setLanguage]      = useState("python");
  const [renderPng] = useState(false); // PNG generated on-demand via download button
  const [activeTab,     setActiveTab]     = useState("both");
  const [selectedModel, setSelectedModel] = useState(null);

  const [history,       setHistory]       = useState([]);
  const [histLoading,   setHistLoading]   = useState(true);
  const [sidebarOpen,   setSidebarOpen]   = useState(true);
  const [activeFolder,  setActiveFolder]  = useState(null);
  const [folders,       setFolders]       = useState([]);

  const [currentDiagId,  setCurrentDiagId]  = useState(null);
  const [currentVersion, setCurrentVersion] = useState(1);

  const fetchHistory = useCallback(async () => {
    setHistLoading(true);
    try {
      const params = activeFolder ? `?folder=${encodeURIComponent(activeFolder)}&limit=40` : "?limit=40";
      const r = await apiFetch(`/api/diagrams${params}`);
      if (r.ok) {
        const data = await r.json();
        setHistory(data);
        setFolders([...new Set(data.map(d => d.folder).filter(Boolean))]);
      }
    } finally { setHistLoading(false); }
  }, [activeFolder]);

  useEffect(() => { fetchHistory(); }, [activeFolder]);

  useEffect(() => {
    if (result?.saved_id) {
      setCurrentDiagId(result.saved_id);
      setCurrentVersion(1);
      fetchHistory();
    }
  }, [result?.saved_id]);

  async function handleGenerate(e) {
    e.preventDefault();
    if (!description.trim()) return;
    await generate({ description, diagramType, language, renderPng });
  }

  async function handleLanguageSwitch(newLang) {
    if (!result) return;
    await regenerateCode({ plantumlCode: result.plantuml_code, diagramType: result.diagram_type, language: newLang });
  }

  async function handleRefine({ diagramId, instruction, language: lang, changeNote }) {
    await refine({ diagramId, instruction, language: lang, changeNote });
  }

  function loadFromHistory(diag) {
    setResult({
      plantuml_code: diag.plantuml_code,
      diagram_type: diag.diagram_type,
      implementation: { code: diag.impl_code || "", language: diag.impl_language || language },
      retrieved_chunks: [],
      backend_used: diag.llm_backend || "saved",
      fallback_used: false,
      saved_id: diag.id,
    });
    setCurrentDiagId(diag.id);
    setCurrentVersion(diag.version || 1);
    setDescription(diag.description);
    setDiagramType(diag.diagram_type);
  }

  function loadFromSearch(item) {
    apiFetch(`/api/diagrams/${item.id}`).then(r => r.json()).then(loadFromHistory);
  }

  function loadFromTemplate({ description: desc, diagramType: dt, plantumlCode }) {
    setDescription(desc);
    setDiagramType(dt);
    setResult({
      plantuml_code: plantumlCode,
      diagram_type: dt,
      implementation: null,
      retrieved_chunks: [],
      backend_used: "template",
      fallback_used: false,
    });
  }

  async function deleteDiagram(id, e) {
    e.stopPropagation();
    await apiFetch(`/api/diagrams/${id}`, { method: "DELETE" });
    setHistory(prev => prev.filter(d => d.id !== id));
    if (currentDiagId === id) { setResult(null); setCurrentDiagId(null); }
  }

  return (
    <div className="app-layout">
      {/* ── Topbar ── */}
      <header className="app-topbar">
        <div className="topbar-l">
          <button className="sidebar-tog" onClick={() => setSidebarOpen(o => !o)}>☰</button>
          <div className="app-logo">
            <span style={{ color: "var(--accent)" }}>⬡</span> UML<strong>Gen</strong>
          </div>
        </div>
        <div className="topbar-center">
          <SearchBar onResult={loadFromSearch} onClear={() => {}} />
        </div>
        <div className="topbar-r">
          <ModelSelector selectedModel={selectedModel} onSelect={setSelectedModel} />
        </div>
      </header>

      <div className="app-body">
        {/* ── Sidebar ── */}
        <aside className={`sidebar ${sidebarOpen ? "open" : "collapsed"}`}>
          <div className="sb-header">
            <span className="sb-label">History</span>
            <button className="sb-new" onClick={() => { setResult(null); setCurrentDiagId(null); setDescription(""); }}>+ New</button>
          </div>

          {folders.length > 0 && (
            <div className="folder-list">
              <button className={`folder-item ${!activeFolder ? "active" : ""}`}
                onClick={() => setActiveFolder(null)}>📁 All diagrams</button>
              {folders.map(f => (
                <button key={f} className={`folder-item ${activeFolder === f ? "active" : ""}`}
                  onClick={() => setActiveFolder(f)}>📂 {f}</button>
              ))}
            </div>
          )}

          <div className="sb-list">
            {histLoading ? (
              <div className="sidebar-empty">Loading…</div>
            ) : history.length === 0 ? (
              <div className="sidebar-empty">No diagrams yet.<br />Generate one!</div>
            ) : history.map(d => (
              <div key={d.id} className={`history-item ${currentDiagId === d.id ? "selected" : ""}`}
                onClick={() => loadFromHistory(d)}>
                <div className="history-item-header">
                  <span className="hist-type-dot"
                    style={{ background: DIAGRAM_TYPES.find(t => t.value === d.diagram_type)?.color || "#64748b" }} />
                  <span className="hist-type">{d.diagram_type}</span>
                  {d.thumb_score > 0 && <span style={{ fontSize: "10px", marginLeft: "auto", color: "#22c55e" }}>👍</span>}
                  {d.thumb_score < 0 && <span style={{ fontSize: "10px", marginLeft: "auto", color: "#ef4444" }}>👎</span>}
                  <button className="hist-del" onClick={(e) => deleteDiagram(d.id, e)}>×</button>
                </div>
                <div className="hist-title">{d.title}</div>
                <div className="hist-meta">
                  {new Date(d.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  {d.impl_language && <span className="hist-lang">{d.impl_language}</span>}
                  {d.folder && <span className="hist-lang">📁 {d.folder}</span>}
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* ── Main ── */}
        <main className="app-main">
          <section className="generator-section">
            <form className="gen-form" onSubmit={handleGenerate}>
              <div className="form-row-grid">
                <div>
                  <div className="form-label">DIAGRAM TYPE</div>
                  <div className="type-row">
                    {DIAGRAM_TYPES.map(t => (
                      <button key={t.value} type="button"
                        className={`type-btn ${diagramType === t.value ? "active" : ""}`}
                        style={diagramType === t.value ? { borderColor: t.color, color: t.color, background: t.color + "18" } : {}}
                        onClick={() => setDiagramType(t.value)}>
                        <span>{t.icon}</span> {t.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="form-label">LANGUAGE</div>
                  <select className="lang-select" value={language} onChange={e => setLanguage(e.target.value)}>
                    {LANGUAGES.map(l => (
                      <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="textarea-wrap">
                <textarea className="desc-input" value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder={`Describe your ${diagramType} diagram in plain English…`}
                  rows={3} required maxLength={2000} />
                <span className="char-count">{description.length}/2000</span>
              </div>

              <div className="form-bottom">
                <button className="btn-generate" type="submit" disabled={loading || !description.trim()}>
                  {loading ? <><span className="spinner" /> Generating…</> : <>⚡ Generate Diagram + Code</>}
                </button>
              </div>
            </form>

            <div className="ex-strip">
              <span className="ex-label">Try:</span>
              {[
                { t: "User login with JWT tokens and refresh rotation",  dt: "sequence" },
                { t: "E-commerce with products, orders and customers",   dt: "class" },
                { t: "Microservices with API gateway and message queue", dt: "component" },
                { t: "Order lifecycle: pending → shipped → delivered",   dt: "state" },
                { t: "Blog schema with users, posts and comments",       dt: "er" },
              ].map((ex, i) => (
                <button key={i} className="example-chip"
                  onClick={() => { setDescription(ex.t); setDiagramType(ex.dt); }}>
                  {ex.t}
                </button>
              ))}
            </div>
          </section>

          {error && <div className="error-bar">⚠ {error}</div>}

          {result ? (
            <section className="results-section">
              <div className="view-toggle">
                {[{ id: "diagram", label: "⬡ Diagram" }, { id: "both", label: "⊞ Both" }, { id: "code", label: "</> Code" }].map(v => (
                  <button key={v.id} className={`view-btn ${activeTab === v.id ? "active" : ""}`}
                    onClick={() => setActiveTab(v.id)}>{v.label}</button>
                ))}
              </div>

              <div className={`panels ${activeTab === "both" ? "panels-split" : ""}`}>
                {(activeTab === "diagram" || activeTab === "both") && (
                  <DiagramPreview
                    code={result.plantuml_code}
                    pngBase64={result.png_base64}
                    renderError={result.render_error}
                    onCodeChange={newCode => setResult(p => ({ ...p, plantuml_code: newCode }))}
                  />
                )}
                {(activeTab === "code" || activeTab === "both") && result.implementation && (
                  <CodePanel
                    code={result.implementation.code}
                    language={result.implementation.language}
                    diagramType={result.diagram_type}
                    plantumlCode={result.plantuml_code}
                    onLanguageChange={handleLanguageSwitch}
                  />
                )}
              </div>

              <RefineBar
                diagramId={currentDiagId}
                language={result.implementation?.language || language}
                onRefine={handleRefine}
                loading={refining}
              />

              <FeedbackBar
                diagramId={currentDiagId}
                onFeedback={submitFeedback}
              />

              <VersionHistory
                diagramId={currentDiagId}
                currentVersion={currentVersion}
                onRestore={fetchHistory}
              />

              {result.retrieved_chunks?.length > 0 && (
                <ContextInspector
                  chunks={result.retrieved_chunks}
                  backend={result.backend_used}
                  fallback={result.fallback_used}
                />
              )}
            </section>
          ) : (
            !loading && <TemplateGallery onSelect={loadFromTemplate} />
          )}
        </main>
      </div>
    </div>
  );
}
