// FeedbackBar.js  –  thumbs up/down + correction input
import { useState } from "react";

export default function FeedbackBar({ diagramId, onFeedback }) {
  const [voted,      setVoted]      = useState(null); // 1 | -1 | null
  const [showFix,    setShowFix]    = useState(false);
  const [correction, setCorrection] = useState("");
  const [submitted,  setSubmitted]  = useState(false);

  async function vote(score) {
    setVoted(score);
    if (score === 1) {
      await onFeedback({ diagramId, score:1, correction:null });
      setSubmitted(true);
    } else {
      setShowFix(true);
    }
  }

  async function submitCorrection() {
    await onFeedback({ diagramId, score:-1, correction });
    setShowFix(false);
    setSubmitted(true);
  }

  if (!diagramId) return null;

  return (
    <div className="feedback-bar">
      {submitted ? (
        <span className="feedback-thanks">✓ Thanks for the feedback — it improves future results</span>
      ) : (
        <>
          <span className="feedback-label">Was this diagram accurate?</span>
          <button
            className={`fb-btn ${voted===1?"active-up":""}`}
            onClick={()=>vote(1)} disabled={voted!==null}>
            👍
          </button>
          <button
            className={`fb-btn ${voted===-1?"active-down":""}`}
            onClick={()=>vote(-1)} disabled={voted!==null}>
            👎
          </button>
        </>
      )}

      {showFix && !submitted && (
        <div className="correction-box">
          <textarea
            className="correction-input"
            placeholder="What was wrong? Describe the correct diagram… (optional)"
            value={correction}
            onChange={e=>setCorrection(e.target.value)}
            rows={2}
          />
          <div style={{display:"flex",gap:"6px",marginTop:"6px"}}>
            <button className="btn-icon" style={{background:"var(--accent)",color:"#fff",border:"none"}}
                    onClick={submitCorrection}>Submit</button>
            <button className="btn-icon" onClick={()=>{setShowFix(false);setSubmitted(true);}}>Skip</button>
          </div>
        </div>
      )}
    </div>
  );
}
