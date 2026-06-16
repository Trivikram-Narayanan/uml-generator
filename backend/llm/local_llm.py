"""
llm/local_llm.py  –  Unified LLM router
Backends: ollama | openai_compat | transformers | gemini | mock

Set LLM_BACKEND in .env. Everything else is wired automatically.
For Gemini also set GEMINI_API_KEY and GEMINI_MODEL.
"""
from __future__ import annotations
import os, re, logging
logger = logging.getLogger(__name__)

BACKEND             = os.getenv("LLM_BACKEND", "ollama").lower()
OLLAMA_URL          = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL        = os.getenv("OLLAMA_MODEL", "codellama:7b-code")
OPENAI_COMPAT_URL   = os.getenv("OPENAI_COMPAT_URL", "http://localhost:1234/v1")
OPENAI_COMPAT_MODEL = os.getenv("OPENAI_COMPAT_MODEL", "local-model")
HF_MODEL_ID         = os.getenv("HF_MODEL_ID", "deepseek-ai/deepseek-coder-6.7b-instruct")
MAX_TOKENS          = int(os.getenv("LLM_MAX_TOKENS", "1024"))
TEMPERATURE         = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_RETRIES         = int(os.getenv("LLM_MAX_RETRIES", "3"))

CHAT_MODEL_HINTS = ["instruct","chat","llama3","qwen","phi3","mistral","deepseek-v2","gemini"]


# ── Extraction / validation ───────────────────────────────────────────────────

def extract_plantuml(raw: str) -> str | None:
    raw = re.sub(r"```(?:plantuml|uml)?", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```", "")
    m = re.search(r"(@startuml.*?@enduml)", raw, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None

def is_valid_plantuml(code: str) -> bool:
    if not code: return False
    low = code.lower()
    return "@startuml" in low and "@enduml" in low

def _fallback(description: str, diagram_type: str) -> str:
    stubs = {
        "sequence":  f"@startuml\nnote over A: {description[:80]}\n@enduml",
        "class":     f"@startuml\nclass Placeholder {{\n  +info: String\n}}\nnote right: {description[:80]}\n@enduml",
        "usecase":   f'@startuml\nactor User\nusecase "{description[:60]}" as UC1\nUser --> UC1\n@enduml',
        "activity":  f"@startuml\nstart\n:{description[:80]};\nstop\n@enduml",
        "component": f"@startuml\n[Component] --> [Other]\nnote right: {description[:80]}\n@enduml",
        "state":     f"@startuml\n[*] --> State1\nState1 --> [*]\nnote right: {description[:80]}\n@enduml",
        "er":        f"@startuml\nentity Entity {{\n  * id : UUID <<PK>>\n}}\nnote right: {description[:80]}\n@enduml",
    }
    return stubs.get(diagram_type, stubs["sequence"])


# ── Raw generators ────────────────────────────────────────────────────────────

def _ollama(prompt: str) -> str:
    import httpx
    r = httpx.post(f"{OLLAMA_URL}/api/generate", json={
        "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": TEMPERATURE, "num_predict": MAX_TOKENS, "stop": ["@enduml"]},
    }, timeout=180)
    r.raise_for_status()
    raw = r.json().get("response","")
    if "@startuml" in raw.lower() and "@enduml" not in raw.lower():
        raw += "\n@enduml"
    return raw

def _openai_compat(prompt: str) -> str:
    import httpx
    is_chat = any(h in OPENAI_COMPAT_MODEL.lower() for h in CHAT_MODEL_HINTS)
    if is_chat:
        r = httpx.post(f"{OPENAI_COMPAT_URL}/chat/completions", json={
            "model": OPENAI_COMPAT_MODEL,
            "messages": [{"role":"user","content":prompt}],
            "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
        }, timeout=180)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    else:
        r = httpx.post(f"{OPENAI_COMPAT_URL}/completions", json={
            "model": OPENAI_COMPAT_MODEL, "prompt": prompt,
            "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE, "stop":["@enduml"],
        }, timeout=180)
        r.raise_for_status()
        raw = r.json()["choices"][0]["text"]
        if "@startuml" in raw.lower() and "@enduml" not in raw.lower():
            raw += "\n@enduml"
        return raw

def _transformers(prompt: str) -> str:
    from functools import lru_cache
    @lru_cache(maxsize=1)
    def _load():
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        tok = AutoTokenizer.from_pretrained(HF_MODEL_ID, trust_remote_code=True)
        mdl = AutoModelForCausalLM.from_pretrained(
            HF_MODEL_ID,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto", trust_remote_code=True,
        )
        return tok, mdl
    tok, mdl = _load()
    import torch
    text = tok.apply_chat_template([{"role":"user","content":prompt}],
        tokenize=False, add_generation_prompt=True) \
        if (hasattr(tok,"apply_chat_template") and tok.chat_template) else prompt
    inp = tok(text, return_tensors="pt").to(mdl.device)
    with torch.no_grad():
        out = mdl.generate(**inp, max_new_tokens=MAX_TOKENS,
            temperature=TEMPERATURE, do_sample=TEMPERATURE>0,
            pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True)

def _gemini(prompt: str) -> str:
    from llm.gemini import generate_with_gemini
    return generate_with_gemini(prompt)

_MOCK_STUBS = {
    "sequence": """\
@startuml
actor User
participant Browser
participant APIServer
participant Database

User -> Browser: submit request
Browser -> APIServer: POST /api/action
activate APIServer
APIServer -> Database: query data
Database --> APIServer: result set
APIServer -> APIServer: process result
APIServer --> Browser: 200 OK + payload
Browser --> User: render response
deactivate APIServer
@enduml""",

    "class": """\
@startuml
class Entity {
  +id: UUID
  +createdAt: DateTime
  +updatedAt: DateTime
  +save(): void
  +delete(): void
}

class ServiceLayer {
  -repo: Repository
  +findById(id: UUID): Entity
  +create(data: dict): Entity
  +update(id: UUID, data: dict): Entity
}

interface Repository {
  +findById(id: UUID): Entity
  +findAll(): List<Entity>
  +save(entity: Entity): void
  +delete(id: UUID): void
}

ServiceLayer --> Repository : uses
Repository <|.. DatabaseRepository
@enduml""",

    "usecase": """\
@startuml
left to right direction
actor User
actor Admin

rectangle System {
  usecase "View Dashboard" as UC1
  usecase "Create Record" as UC2
  usecase "Edit Record" as UC3
  usecase "Delete Record" as UC4
  usecase "Manage Users" as UC5
  usecase "Authenticate" as UC6
}

User --> UC1
User --> UC2
User --> UC3
Admin --> UC4
Admin --> UC5
UC1 .> UC6 : <<include>>
UC2 .> UC6 : <<include>>
@enduml""",

    "activity": """\
@startuml
start
:Receive input;
if (Valid input?) then (yes)
  :Process request;
  if (Success?) then (yes)
    :Save result;
    :Send notification;
    stop
  else (no)
    :Log error;
    :Return error response;
    stop
  endif
else (no)
  :Return validation error;
  stop
endif
@enduml""",

    "component": """\
@startuml
package "Client" {
  [Web App] as WEB
  [Mobile App] as MOB
}

package "API Layer" {
  [Gateway] as GW
  [Auth Service] as AUTH
}

package "Core Services" {
  [Business Service] as BIZ
  [Notification Service] as NOTIF
}

database "Primary DB" as DB
queue "Message Queue" as MQ

WEB --> GW
MOB --> GW
GW --> AUTH
GW --> BIZ
BIZ --> MQ
MQ --> NOTIF
BIZ --> DB
AUTH --> DB
@enduml""",

    "state": """\
@startuml
[*] --> Draft

Draft --> Pending : submit
Draft --> Cancelled : cancel

Pending --> Active : approve
Pending --> Rejected : reject
Pending --> Cancelled : cancel

Active --> Completed : finish
Active --> Cancelled : cancel

Rejected --> Draft : revise

Completed --> [*]
Cancelled --> [*]
@enduml""",

    "er": """\
@startuml
entity User {
  * id : UUID <<PK>>
  --
  * email : VARCHAR(255)
  * username : VARCHAR(80)
  * passwordHash : VARCHAR(255)
  createdAt : TIMESTAMP
}

entity Record {
  * id : UUID <<PK>>
  --
  * title : VARCHAR(255)
  * content : TEXT
  * userId : UUID <<FK>>
  status : ENUM
  createdAt : TIMESTAMP
}

entity Tag {
  * id : UUID <<PK>>
  --
  * name : VARCHAR(60)
}

entity RecordTag {
  * recordId : UUID <<FK>>
  * tagId : UUID <<FK>>
}

User ||--o{ Record : owns
Record }o--o{ Tag : tagged_with
Record ||--o{ RecordTag : has
Tag ||--o{ RecordTag : has
@enduml""",
}


def _mock(prompt: str) -> str:
    import re
    m = re.search(r"Diagram type:\s*(\w+)", prompt, re.IGNORECASE)
    dtype = m.group(1).lower() if m else "sequence"
    return _MOCK_STUBS.get(dtype, _MOCK_STUBS["sequence"])


# ── Retry loop ────────────────────────────────────────────────────────────────

def _raw_generate(prompt: str) -> str:
    dispatch = {"ollama": _ollama, "openai_compat": _openai_compat,
                "transformers": _transformers, "gemini": _gemini, "mock": _mock}
    fn = dispatch.get(BACKEND)
    if not fn:
        raise ValueError(f"Unknown LLM_BACKEND: '{BACKEND}'. Use: {list(dispatch)}")
    return fn(prompt)


def generate_uml(description: str, diagram_type: str, prompt: str) -> dict:
    """
    Generates PlantUML with up to MAX_RETRIES attempts.
    On each failure the error is appended to the prompt so the model self-corrects.
    """
    raw, code, fallback_used = "", "", False
    current_prompt = prompt

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw  = _raw_generate(current_prompt)
            code = extract_plantuml(raw)

            if code and is_valid_plantuml(code):
                logger.info("PlantUML valid on attempt %d", attempt)
                break

            # Inject error back into prompt for next attempt
            error_hint = (
                f"\n\nPREVIOUS ATTEMPT FAILED: The output did not contain a valid "
                f"@startuml...@enduml block. Output was:\n{raw[:300]}\n"
                f"Try again. Output ONLY valid PlantUML starting with @startuml."
            )
            current_prompt = prompt + error_hint
            logger.warning("Attempt %d invalid — retrying with error feedback", attempt)

        except Exception as exc:
            logger.error("LLM attempt %d failed: %s", attempt, exc)
            raw = str(exc)
            error_hint = f"\n\nPREVIOUS ATTEMPT ERRORED: {exc}\nTry again."
            current_prompt = prompt + error_hint

    if not code or not is_valid_plantuml(code):
        logger.warning("All %d attempts failed — using fallback stub", MAX_RETRIES)
        code = _fallback(description, diagram_type)
        fallback_used = True

    return {"code": code, "raw": raw, "backend": BACKEND,
            "fallback": fallback_used, "model": _active_model()}


def _active_model() -> str:
    if BACKEND == "ollama":        return OLLAMA_MODEL
    if BACKEND == "openai_compat": return OPENAI_COMPAT_MODEL
    if BACKEND == "gemini":        return os.getenv("GEMINI_MODEL","gemini-2.0-flash")
    if BACKEND == "transformers":  return HF_MODEL_ID
    return "mock"
