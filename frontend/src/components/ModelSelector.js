// ModelSelector.js  –  switch between Gemini models and local models
import { useState, useEffect } from "react";
import { apiFetch } from "../utils/api";

const GEMINI_MODELS = [
  { id:"gemini-2.0-flash", label:"Gemini 2.0 Flash", tag:"fastest", color:"#4f8ef7" },
  { id:"gemini-1.5-pro",   label:"Gemini 1.5 Pro",   tag:"best quality", color:"#a78bfa" },
  { id:"gemini-1.5-flash", label:"Gemini 1.5 Flash",  tag:"balanced", color:"#22d3ee" },
];

export default function ModelSelector({ selectedModel, onSelect }) {
  const [info, setInfo] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    apiFetch("/api/models").then(r=>r.json()).then(setInfo).catch(()=>{});
  }, []);

  if (!info) return null;

  const isGemini = info.backend === "gemini";
  const activeLabel = isGemini
    ? (GEMINI_MODELS.find(m=>m.id===info.gemini_model)?.label || info.gemini_model)
    : info.active_model;

  return (
    <div className="model-selector-wrap">
      <button className="model-selector-btn" onClick={()=>setOpen(o=>!o)}>
        <span className={`model-dot ${isGemini?"gemini":"local"}`}/>
        <span className="model-name">{activeLabel}</span>
        <span className="model-arrow">{open?"▾":"▸"}</span>
      </button>

      {open && (
        <div className="model-dropdown">
          {isGemini && info.gemini_configured ? (
            <>
              <div className="model-section-label">Gemini (Cloud)</div>
              {GEMINI_MODELS.map(m=>(
                <button key={m.id}
                  className={`model-option ${info.gemini_model===m.id?"active":""}`}
                  onClick={()=>{ onSelect({type:"gemini",model:m.id}); setOpen(false); }}>
                  <span className="model-option-name">{m.label}</span>
                  <span className="model-option-tag" style={{color:m.color}}>{m.tag}</span>
                </button>
              ))}
              <div className="model-divider"/>
            </>
          ) : (
            <div className="model-section-label" style={{color:"var(--text3)"}}>
              Local: {info.active_model}
            </div>
          )}

          {!info.gemini_configured && (
            <div className="model-gemini-cta">
              <span>Add <code>GEMINI_API_KEY</code> to .env to enable Gemini</span>
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer">
                Get free key →
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
