// VersionHistory.js  –  collapsible version list with restore
import { useState, useEffect } from "react";
import { apiFetch } from "../utils/api";

export default function VersionHistory({ diagramId, currentVersion, onRestore }) {
  const [open,     setOpen]     = useState(false);
  const [versions, setVersions] = useState([]);
  const [loading,  setLoading]  = useState(false);

  useEffect(() => {
    if (open && diagramId) fetchVersions();
  }, [open, diagramId]);

  async function fetchVersions() {
    setLoading(true);
    try {
      const r = await apiFetch(`/api/diagrams/${diagramId}/versions`);
      if (r.ok) setVersions(await r.json());
    } finally { setLoading(false); }
  }

  async function restore(versionNum) {
    const r = await apiFetch(`/api/diagrams/${diagramId}/restore/${versionNum}`, { method:"POST" });
    if (r.ok) { if (onRestore) onRestore(); setOpen(false); }
  }

  if (!diagramId) return null;

  return (
    <div className="version-history">
      <button className="inspector-toggle" onClick={()=>setOpen(o=>!o)}>
        {open?"▾":"▸"} Version History
        <span className="inspector-meta">v{currentVersion} · {versions.length} saved</span>
      </button>
      {open && (
        <div className="chunk-list">
          {loading ? (
            <div style={{padding:"12px",color:"var(--text3)",fontSize:"12px"}}>Loading…</div>
          ) : versions.length === 0 ? (
            <div style={{padding:"12px",color:"var(--text3)",fontSize:"12px"}}>No versions yet</div>
          ) : versions.map(v => (
            <div key={v.id} className="chunk-item" style={{display:"flex",alignItems:"center",gap:"8px"}}>
              <div style={{flex:1}}>
                <div className="chunk-meta">
                  <span className="badge">v{v.version}</span>
                  {v.impl_language && <span className="badge">{v.impl_language}</span>}
                  <span className="score">{new Date(v.created_at).toLocaleDateString()}</span>
                </div>
                {v.change_note && (
                  <div style={{fontSize:"11px",color:"var(--text3)",marginTop:"3px"}}>{v.change_note}</div>
                )}
              </div>
              {v.version !== currentVersion && (
                <button className="btn-icon" onClick={()=>restore(v.version)}>↩ Restore</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
