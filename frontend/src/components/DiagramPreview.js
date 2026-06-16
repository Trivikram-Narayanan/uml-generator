// DiagramPreview.js  –  PlantUML source + Monaco editor + preview + export
import { useState } from "react";
import Editor from "@monaco-editor/react";

const KROKI_URL = process.env.REACT_APP_KROKI_URL || "https://kroki.io";

export default function DiagramPreview({ code, pngBase64, renderError, onCodeChange }) {
  const [editMode,    setEditMode]    = useState(false);
  const [editedCode,  setEditedCode]  = useState(code);
  const [svgContent,  setSvgContent]  = useState(null);
  const [svgLoading,  setSvgLoading]  = useState(false);
  const [svgError,    setSvgError]    = useState(null);
  const [copied,      setCopied]      = useState(false);
  const [pngLoading,  setPngLoading]  = useState(false);

  // Keep editedCode in sync when parent updates code
  if (editedCode !== code && !editMode) setEditedCode(code);

  async function fetchSvg() {
    setSvgLoading(true); setSvgError(null);
    try {
      const r = await fetch(`${KROKI_URL}/plantuml/svg`, {
        method: "POST", headers: { "Content-Type": "text/plain" }, body: editedCode,
      });
      if (!r.ok) throw new Error(`Kroki ${r.status}`);
      setSvgContent(await r.text());
    } catch (e) { setSvgError(e.message); }
    finally { setSvgLoading(false); }
  }

  async function downloadPng() {
    // If we already have a server-rendered base64 PNG, use that
    if (pngBase64) {
      const a = document.createElement("a");
      a.href = `data:image/png;base64,${pngBase64}`;
      a.download = "diagram.png";
      a.click();
      return;
    }
    // Otherwise fetch SVG from Kroki and convert via canvas (2× retina)
    setPngLoading(true); setSvgError(null);
    try {
      const r = await fetch(`${KROKI_URL}/plantuml/svg`, {
        method: "POST", headers: { "Content-Type": "text/plain" }, body: editedCode,
      });
      if (!r.ok) throw new Error(`Kroki ${r.status}`);
      const svg = await r.text();

      const blob = new Blob([svg], { type: "image/svg+xml" });
      const blobUrl = URL.createObjectURL(blob);
      const img = new Image();

      img.onload = () => {
        const scale = 2;
        const canvas = document.createElement("canvas");
        canvas.width  = img.naturalWidth  * scale;
        canvas.height = img.naturalHeight * scale;
        const ctx = canvas.getContext("2d");
        ctx.scale(scale, scale);
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(blobUrl);
        const a = document.createElement("a");
        a.href = canvas.toDataURL("image/png");
        a.download = "diagram.png";
        a.click();
        setPngLoading(false);
      };
      img.onerror = () => { setSvgError("PNG conversion failed"); setPngLoading(false); };
      img.src = blobUrl;
    } catch (e) { setSvgError(e.message); setPngLoading(false); }
  }

  function saveEdit() {
    if (onCodeChange) onCodeChange(editedCode);
    setEditMode(false);
    setSvgContent(null); // reset preview to force re-render
  }

  function copy() {
    navigator.clipboard.writeText(editedCode||"");
    setCopied(true); setTimeout(()=>setCopied(false),1800);
  }

  function downloadPuml() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([editedCode], { type: "text/plain" }));
    a.download = "diagram.puml"; a.click();
  }

  function downloadSvg() {
    const src = svgContent;
    if (!src) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([src], { type: "image/svg+xml" }));
    a.download = "diagram.svg"; a.click();
  }

  function downloadMd() {
    const md = `## Diagram\n\n\`\`\`plantuml\n${editedCode}\n\`\`\`\n`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    a.download = "diagram.md"; a.click();
  }

  if (!code) return null;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">PlantUML</span>
        <div className="panel-actions">
          <button className="btn-icon" onClick={()=>{setEditMode(e=>!e);setSvgContent(null);}}>
            {editMode?"👁 View":"✏ Edit"}
          </button>
          <button className="btn-icon" onClick={copy}>{copied ? "✓" : "⎘"} Copy</button>
          <button className="btn-icon" onClick={downloadPuml}>↓ .puml</button>
          <button className="btn-icon" onClick={downloadMd}>↓ .md</button>
          {svgContent && <button className="btn-icon" onClick={downloadSvg}>↓ .svg</button>}
          <button className="btn-icon" onClick={downloadPng} disabled={pngLoading}
            title="Download diagram as PNG (fetches from Kroki)">
            {pngLoading ? <><span className="spinner-sm"/> PNG…</> : "↓ .png"}
          </button>
        </div>
      </div>

      {editMode ? (
        <div style={{display:"flex",flexDirection:"column"}}>
          <Editor
            height="320px"
            defaultLanguage="plaintext"
            value={editedCode}
            onChange={v => setEditedCode(v||"")}
            theme="vs-dark"
            options={{ fontSize:12, minimap:{enabled:false}, scrollBeyondLastLine:false,
                       wordWrap:"on", lineNumbers:"on", padding:{top:8} }}
          />
          <div style={{padding:"8px 12px",display:"flex",gap:"8px",
                       borderTop:"0.5px solid var(--border)",background:"var(--surface2)"}}>
            <button className="btn-icon" style={{background:"var(--accent)",color:"#fff",border:"none"}}
                    onClick={saveEdit}>✓ Apply changes</button>
            <button className="btn-icon" onClick={()=>{setEditMode(false);setEditedCode(code);}}>
              ✕ Cancel
            </button>
          </div>
        </div>
      ) : (
        <pre className="code-block plantuml-code"><code>{editedCode}</code></pre>
      )}

      <div className="preview-area">
        {pngBase64 ? (
          <img src={`data:image/png;base64,${pngBase64}`} alt="UML Diagram" className="diagram-img"/>
        ) : svgContent ? (
          <div className="svg-wrap" dangerouslySetInnerHTML={{__html:svgContent}}/>
        ) : (
          <div className="render-prompt">
            {svgError && <p className="warn-text">⚠ {svgError}</p>}
            <button className="btn-render" onClick={fetchSvg} disabled={svgLoading}>
              {svgLoading ? <><span className="spinner-sm"/> Rendering…</> : "▶ Render Preview"}
            </button>
            <span className="render-note">via kroki.io · self-host: <code>docker run yuzutech/kroki</code></span>
          </div>
        )}
        {renderError && <p className="warn-text">PNG error: {renderError}</p>}
      </div>
    </div>
  );
}
