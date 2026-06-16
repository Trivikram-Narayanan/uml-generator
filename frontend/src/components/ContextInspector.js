// src/components/ContextInspector.js
import { useState } from "react";

export default function ContextInspector({ chunks, backend, fallback }) {
  const [open, setOpen] = useState(false);
  if (!chunks || chunks.length === 0) return null;
  return (
    <div className="inspector">
      <button className="inspector-toggle" onClick={() => setOpen(o => !o)}>
        {open ? "▾" : "▸"} RAG Inspector
        <span className="inspector-meta">
          {chunks.length} chunks · {backend}
          {fallback && <span className="badge-warn"> FALLBACK</span>}
        </span>
      </button>
      {open && (
        <div className="chunk-list">
          {chunks.map((c, i) => (
            <div key={i} className="chunk-item">
              <div className="chunk-meta">
                <span className="badge">{c.content_type}</span>
                <span className="badge">{c.diagram_type}</span>
                <span className="badge dim">{c.source}</span>
                <span className="score">sim {c.score.toFixed(3)}</span>
              </div>
              <pre className="chunk-text">{c.text}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
