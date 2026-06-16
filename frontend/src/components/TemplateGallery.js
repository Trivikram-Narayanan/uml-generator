// TemplateGallery.js  –  shown on empty state, lets user pick a template
import { useState, useEffect } from "react";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";
const CATEGORY_COLORS = {
  "Auth":"#4f8ef7","E-Commerce":"#a78bfa","Architecture":"#06b6d4",
  "Database":"#22c55e","General":"#f59e0b",
};

export default function TemplateGallery({ onSelect }) {
  const [templates, setTemplates] = useState([]);
  const [category,  setCategory]  = useState("All");

  useEffect(() => {
    fetch(`${API}/api/templates`).then(r=>r.json()).then(setTemplates).catch(()=>{});
  }, []);

  const categories = ["All", ...new Set(templates.map(t=>t.category).filter(Boolean))];
  const filtered   = category==="All" ? templates : templates.filter(t=>t.category===category);

  async function useTemplate(t) {
    await fetch(`${API}/api/templates/${t.id}/use`, { method:"POST" });
    onSelect({ description:t.description, diagramType:t.diagram_type, plantumlCode:t.plantuml_code });
  }

  return (
    <div className="template-gallery">
      <div className="gallery-header">
        <div className="section-label" style={{marginBottom:0}}>Templates</div>
        <p style={{fontSize:"12px",color:"var(--text3)",marginTop:"4px"}}>
          Start from a template or describe your own diagram above
        </p>
      </div>
      <div className="category-tabs">
        {categories.map(c=>(
          <button key={c}
            className={`cat-tab ${category===c?"active":""}`}
            style={category===c?{borderColor:CATEGORY_COLORS[c]||"var(--accent)",
                                  color:CATEGORY_COLORS[c]||"var(--accent)"}:{}}
            onClick={()=>setCategory(c)}>{c}</button>
        ))}
      </div>
      <div className="template-grid">
        {filtered.map(t=>(
          <div key={t.id} className="template-card" onClick={()=>useTemplate(t)}>
            <div className="template-card-header">
              <span className="template-type-dot" style={{
                background: {sequence:"#4f8ef7",class:"#a78bfa",usecase:"#22c55e",
                  activity:"#f59e0b",component:"#06b6d4",state:"#f97316",er:"#ec4899"}[t.diagram_type]||"#64748b"
              }}/>
              <span className="template-type">{t.diagram_type}</span>
              {t.category && (
                <span className="template-cat" style={{color:CATEGORY_COLORS[t.category]||"var(--text3)"}}>
                  {t.category}
                </span>
              )}
            </div>
            <div className="template-title">{t.title}</div>
            <div className="template-desc">{t.description}</div>
            <div className="template-footer">
              <span className="template-uses">{t.use_count} uses</span>
              <span className="template-cta">Use template →</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
