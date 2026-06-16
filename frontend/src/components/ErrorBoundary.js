// ErrorBoundary.js  –  catches render errors so the whole app doesn't crash
import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding:"2rem", display:"flex", flexDirection:"column",
          alignItems:"center", gap:"12px", color:"var(--text2,#94a3b8)",
          fontFamily:"'Space Mono',monospace", fontSize:"13px",
        }}>
          <div style={{fontSize:"24px",opacity:.4}}>⚠</div>
          <strong style={{color:"var(--text,#e2e8f0)"}}>Something went wrong</strong>
          <p style={{fontSize:"12px",color:"var(--text3,#64748b)",maxWidth:"360px",textAlign:"center",lineHeight:1.6}}>
            {this.state.error?.message || "An unexpected error occurred in this panel."}
          </p>
          <button
            onClick={() => this.setState({ hasError:false, error:null })}
            style={{background:"transparent",border:"1px solid rgba(255,255,255,.12)",
                    color:"var(--text2,#94a3b8)",borderRadius:"6px",padding:"5px 14px",
                    cursor:"pointer",fontSize:"12px"}}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
