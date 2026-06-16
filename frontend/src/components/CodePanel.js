// src/components/CodePanel.js
import { useState } from "react";

const LANG_META = {
  python:     { label:"Python",     ext:".py",    color:"#4f8ef7" },
  javascript: { label:"JavaScript", ext:".js",    color:"#f59e0b" },
  typescript: { label:"TypeScript", ext:".ts",    color:"#6366f1" },
  java:       { label:"Java",       ext:".java",  color:"#ef4444" },
  go:         { label:"Go",         ext:".go",    color:"#22d3ee" },
  rust:       { label:"Rust",       ext:".rs",    color:"#f97316" },
  csharp:     { label:"C#",         ext:".cs",    color:"#8b5cf6" },
  cpp:        { label:"C++",        ext:".cpp",   color:"#64748b" },
  ruby:       { label:"Ruby",       ext:".rb",    color:"#e11d48" },
  kotlin:     { label:"Kotlin",     ext:".kt",    color:"#7c3aed" },
  swift:      { label:"Swift",      ext:".swift", color:"#f59e0b" },
};

export default function CodePanel({ code, language, diagramType, plantumlCode, onLanguageChange }) {
  const [copied,    setCopied]    = useState(false);
  const [switching, setSwitching] = useState(false);

  const meta = LANG_META[language] || { label: language, ext: ".txt", color: "#64748b" };

  function copy() {
    navigator.clipboard.writeText(code || "");
    setCopied(true); setTimeout(() => setCopied(false), 1800);
  }
  function download() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([code], { type: "text/plain" }));
    a.download = `implementation${meta.ext}`; a.click();
  }
  async function switchLang(lang) {
    if (lang === language || switching) return;
    setSwitching(true);
    await onLanguageChange(lang);
    setSwitching(false);
  }

  if (!code) return null;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">
          Implementation
          <span
            className="lang-badge"
            style={{ background: meta.color + "20", color: meta.color, borderColor: meta.color + "40", border: "1px solid" }}
          >
            {meta.label}
          </span>
        </span>
        <div className="panel-actions">
          <button className="btn-icon" onClick={copy} disabled={switching}>{copied ? "✓" : "⎘"} Copy</button>
          <button className="btn-icon" onClick={download} disabled={switching}>↓ {meta.ext}</button>
        </div>
      </div>

      <div className="lang-switcher">
        {Object.entries(LANG_META).map(([lang, m]) => (
          <button
            key={lang}
            className={`lang-btn ${lang === language ? "active" : ""}`}
            style={lang === language ? { color: m.color, borderColor: m.color + "60" } : {}}
            onClick={() => switchLang(lang)}
            disabled={switching}
          >{m.label}</button>
        ))}
      </div>

      {switching ? (
        <div className="code-loading">
          <span className="spinner-sm" /> Generating {LANG_META[language]?.label || language} code…
        </div>
      ) : (
        <pre className="code-block impl-code"><code>{code}</code></pre>
      )}
    </div>
  );
}
