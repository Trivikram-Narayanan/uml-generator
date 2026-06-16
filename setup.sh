#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  UMLGen  –  One-shot setup script
#  Runs everything: venv, deps, knowledge base, starts the server
#
#  Usage:
#    chmod +x setup.sh
#    ./setup.sh                  # uses mock backend (no model needed)
#    ./setup.sh --model ollama   # uses Ollama (must have it installed)
# ═══════════════════════════════════════════════════════════════════

set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${BLUE}[umlgen]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

MODEL_BACKEND=${1:-"--mock"}

log "═══════════════════════════════════════"
log "  UMLGen Setup"
log "═══════════════════════════════════════"

# ── 1. Backend setup ────────────────────────────────────────────────
cd "$(dirname "$0")/backend"

log "Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
ok "Virtual environment ready"

log "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Dependencies installed"

# ── 2. .env ─────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  # Generate a random SECRET_KEY
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i.bak "s/change-this-to-a-random-32-byte-hex-string/$SECRET/" .env
  rm -f .env.bak

  if [ "$MODEL_BACKEND" = "--mock" ]; then
    sed -i.bak "s/^LLM_BACKEND=ollama/LLM_BACKEND=mock/" .env
    rm -f .env.bak
    warn "Using MOCK backend. Diagrams are hardcoded stubs."
    warn "To use a real model: set LLM_BACKEND=ollama in backend/.env"
  fi
  ok ".env created with random SECRET_KEY"
else
  ok ".env already exists — skipping"
fi

# ── 3. Knowledge base ingestion ─────────────────────────────────────
if [ ! -d "data/chroma" ]; then
  log "Building knowledge base (first-time setup)..."
  python -m scripts.ingest
  ok "Knowledge base ready"
else
  ok "Knowledge base already exists — skipping"
fi

# ── 4. Frontend setup ───────────────────────────────────────────────
cd ../frontend
log "Installing frontend dependencies..."
npm install --silent
ok "Frontend dependencies installed"

log "═══════════════════════════════════════"
ok "Setup complete!"
echo ""
echo "  To start the backend:   cd backend && source .venv/bin/activate && uvicorn api.main:app --reload"
echo "  To start the frontend:  cd frontend && npm start"
echo ""
echo "  Or start everything:    docker compose up --build"
echo ""
