import { useState, useCallback } from "react";
import { apiFetch } from "../utils/api";

export function useGenerate() {
  const [loading,  setLoading]  = useState(false);
  const [refining, setRefining] = useState(false);
  const [error,    setError]    = useState(null);
  const [result,   setResult]   = useState(null);

  const generate = useCallback(async ({ description, diagramType, language, renderPng = false, folder, workspaceId }) => {
    setLoading(true); setError(null); setResult(null);
    try {
      const resp = await apiFetch("/api/diagrams/generate-full", {
        method: "POST",
        body: JSON.stringify({ description, diagram_type: diagramType, language,
          render_png: renderPng, save: true, folder, workspace_id: workspaceId }),
      });
      if (!resp.ok) { const b = await resp.json().catch(() => ({})); throw new Error(b.detail || `Error ${resp.status}`); }
      setResult(await resp.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  const refine = useCallback(async ({ diagramId, instruction, language, changeNote }) => {
    setRefining(true); setError(null);
    try {
      const resp = await apiFetch("/api/diagrams/refine", {
        method: "POST",
        body: JSON.stringify({ diagram_id: diagramId, instruction, language, change_note: changeNote }),
      });
      if (!resp.ok) { const b = await resp.json().catch(() => ({})); throw new Error(b.detail || `Error ${resp.status}`); }
      const data = await resp.json();
      setResult(prev => ({ ...prev, plantuml_code: data.plantuml_code, implementation: data.implementation }));
    } catch (e) { setError(e.message); }
    finally { setRefining(false); }
  }, []);

  const regenerateCode = useCallback(async ({ plantumlCode, diagramType, language }) => {
    try {
      const resp = await apiFetch("/api/diagrams/generate-code", {
        method: "POST",
        body: JSON.stringify({ plantuml_code: plantumlCode, diagram_type: diagramType, language }),
      });
      if (!resp.ok) return null;
      const data = await resp.json();
      setResult(prev => ({ ...prev, implementation: data }));
      return data;
    } catch { return null; }
  }, []);

  const submitFeedback = useCallback(async ({ diagramId, score, correction }) => {
    await apiFetch("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ diagram_id: diagramId, score, correction }),
    });
  }, []);

  return { loading, refining, error, result, setResult, generate, refine, regenerateCode, submitFeedback };
}
