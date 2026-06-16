// SearchBar.js  –  full-text search + type/tag filters
import { useState, useEffect, useRef } from "react";
import { apiFetch } from "../utils/api";

export default function SearchBar({ onResult, onClear }) {
  const [query,        setQuery]        = useState("");
  const [diagramType,  setDiagramType]  = useState("");
  const [open,         setOpen]         = useState(false);
  const [results,      setResults]      = useState([]);
  const [loading,      setLoading]      = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (!query && !diagramType) { setResults([]); return; }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(doSearch, 280);
    return () => clearTimeout(debounceRef.current);
  }, [query, diagramType]);

  async function doSearch() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query)       params.set("q", query);
      if (diagramType) params.set("diagram_type", diagramType);
      const r = await apiFetch(`/api/search?${params}`);
      if (r.ok) setResults(await r.json());
    } finally { setLoading(false); }
  }

  function clear() {
    setQuery(""); setDiagramType(""); setResults([]);
    if (onClear) onClear();
  }

  const TYPES = ["sequence","class","usecase","activity","component","state","er"];
  const TYPE_COLORS = {sequence:"#4f8ef7",class:"#a78bfa",usecase:"#22c55e",
    activity:"#f59e0b",component:"#06b6d4",state:"#f97316",er:"#ec4899"};

  return (
    <div className="search-wrap">
      <div className="search-row">
        <div className="search-input-wrap">
          <span className="search-icon">⌕</span>
          <input
            className="search-input"
            value={query}
            onChange={e=>setQuery(e.target.value)}
            onFocus={()=>setOpen(true)}
            placeholder="Search diagrams…"
          />
          {(query||diagramType) && (
            <button className="search-clear" onClick={clear}>×</button>
          )}
        </div>
        <div className="type-filter-row">
          {TYPES.map(t=>(
            <button key={t}
              className={`type-filter-btn ${diagramType===t?"active":""}`}
              style={diagramType===t?{borderColor:TYPE_COLORS[t],color:TYPE_COLORS[t],background:TYPE_COLORS[t]+"18"}:{}}
              onClick={()=>setDiagramType(d=>d===t?"":t)}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {open && results.length > 0 && (
        <div className="search-results">
          {loading && <div className="search-loading">Searching…</div>}
          {results.map(r=>(
            <div key={r.id} className="search-result-item"
              onClick={()=>{ onResult(r); setOpen(false); }}>
              <div style={{display:"flex",alignItems:"center",gap:"6px",marginBottom:"3px"}}>
                <span className="dot-type" style={{background:TYPE_COLORS[r.diagram_type]||"#64748b",width:"7px",height:"7px",borderRadius:"50%",display:"inline-block"}}/>
                <span style={{fontSize:"11px",color:"var(--text3)",fontFamily:"var(--mono)",textTransform:"uppercase"}}>{r.diagram_type}</span>
                {r.impl_language && <span className="hist-lang">{r.impl_language}</span>}
                <span style={{marginLeft:"auto",fontSize:"10px",color:"var(--text3)"}}>
                  {new Date(r.updated_at).toLocaleDateString()}
                </span>
              </div>
              <div style={{fontSize:"13px",color:"var(--text)",fontWeight:"500"}}>{r.title}</div>
              <div style={{fontSize:"11px",color:"var(--text3)",marginTop:"2px",
                whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{r.description}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
