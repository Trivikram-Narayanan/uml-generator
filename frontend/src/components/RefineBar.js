// RefineBar.js  –  "Fix this" iterative refinement input
import { useState } from "react";

export default function RefineBar({ diagramId, language, onRefine, loading }) {
  const [instruction, setInstruction] = useState("");
  const [expanded,    setExpanded]    = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    if (!instruction.trim()) return;
    onRefine({ diagramId, instruction, language, changeNote: instruction.slice(0,100) });
    setInstruction("");
  }

  if (!diagramId) return null;

  return (
    <div className="refine-bar">
      <button className="refine-toggle" onClick={()=>setExpanded(e=>!e)}>
        <span>✏ Refine diagram</span>
        <span style={{marginLeft:"auto",fontSize:"10px",color:"var(--text3)"}}>
          {expanded?"▾":"▸"} Apply a change without regenerating
        </span>
      </button>
      {expanded && (
        <form className="refine-form" onSubmit={handleSubmit}>
          <input
            className="refine-input"
            value={instruction}
            onChange={e=>setInstruction(e.target.value)}
            placeholder='e.g. "Add a cache layer between Gateway and Service" or "Remove the Database participant"'
            required
          />
          <button className="btn-generate" type="submit" disabled={loading||!instruction.trim()}>
            {loading ? <><span className="spinner"/> Refining…</> : "⚡ Apply"}
          </button>
        </form>
      )}
    </div>
  );
}
