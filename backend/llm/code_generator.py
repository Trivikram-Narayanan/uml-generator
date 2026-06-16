"""
llm/code_generator.py  –  Implementation code generation
Same backend as local_llm.py. Supports Gemini + all local models.
"""
from __future__ import annotations
import os, re, logging
logger = logging.getLogger(__name__)

BACKEND             = os.getenv("LLM_BACKEND","ollama").lower()
OLLAMA_URL          = os.getenv("OLLAMA_URL","http://localhost:11434")
OLLAMA_MODEL        = os.getenv("OLLAMA_MODEL","codellama:7b-code")
OPENAI_COMPAT_URL   = os.getenv("OPENAI_COMPAT_URL","http://localhost:1234/v1")
OPENAI_COMPAT_MODEL = os.getenv("OPENAI_COMPAT_MODEL","local-model")
HF_MODEL_ID         = os.getenv("HF_MODEL_ID","deepseek-ai/deepseek-coder-6.7b-instruct")
MAX_TOKENS          = int(os.getenv("LLM_MAX_TOKENS","1500"))
TEMPERATURE         = float(os.getenv("LLM_CODE_TEMPERATURE","0.15"))
CHAT_MODEL_HINTS    = ["instruct","chat","llama3","qwen","phi3","mistral","deepseek-v2"]

SUPPORTED_LANGUAGES = [
    "python","javascript","typescript","java",
    "go","rust","csharp","cpp","ruby","kotlin","swift",
]

LANG_NOTES = {
    "python":     "Python 3.11+. dataclasses/classes, full type hints, no external libs.",
    "javascript": "ES2022 classes with JSDoc. No frameworks or external libs.",
    "typescript": "TypeScript 5+, strict. Interfaces where appropriate. No external libs.",
    "java":       "Java 17+. Records for immutable data. No external libs.",
    "go":         "Idiomatic Go 1.22. Structs and interfaces. stdlib only.",
    "rust":       "Rust 2021. Derive Debug/Clone. std only.",
    "csharp":     "C# 12, .NET 8. Nullable refs on. No external libs.",
    "cpp":        "C++20. Header-style inline. STL only.",
    "ruby":       "Ruby 3.3+. attr_accessor where appropriate. No gems.",
    "kotlin":     "Kotlin 2.0. Data classes for value objects. No external libs.",
    "swift":      "Swift 5.10. Protocols and structs. Foundation only.",
}

SYSTEM = """\
You are an expert software engineer. Output ONLY raw implementation code — no markdown fences, no explanations.
Rules:
1. Implement every class, method, interface shown in the UML diagram.
2. Add a one-line comment on each class/function.
3. Write realistic method bodies, not stubs.
4. For sequence diagrams: generate the classes involved with the exact methods called.
5. For ER diagrams: generate typed model/entity classes matching the schema.
6. For state diagrams: implement a proper state machine.
7. For activity diagrams: implement the workflow as a function or class.
"""

def build_prompt(plantuml_code: str, diagram_type: str, language: str) -> str:
    return (f"{SYSTEM}\n\n=== UML ({diagram_type.upper()}) ===\n{plantuml_code}\n\n"
            f"=== TARGET: {language.upper()} ===\n{LANG_NOTES.get(language,'')}\n\n"
            f"Generate {language} now:")

def clean(raw: str) -> str:
    raw = re.sub(r"```[a-zA-Z]*\n?","",raw)
    return raw.replace("```","").strip()

# ── Backends ──────────────────────────────────────────────────────────────────

def _ollama(p):
    import httpx
    r = httpx.post(f"{OLLAMA_URL}/api/generate", json={
        "model":OLLAMA_MODEL,"prompt":p,"stream":False,
        "options":{"temperature":TEMPERATURE,"num_predict":MAX_TOKENS}},timeout=180)
    r.raise_for_status(); return r.json().get("response","")

def _openai_compat(p):
    import httpx
    is_chat = any(h in OPENAI_COMPAT_MODEL.lower() for h in CHAT_MODEL_HINTS)
    if is_chat:
        r = httpx.post(f"{OPENAI_COMPAT_URL}/chat/completions", json={
            "model":OPENAI_COMPAT_MODEL,"messages":[{"role":"user","content":p}],
            "max_tokens":MAX_TOKENS,"temperature":TEMPERATURE},timeout=180)
        r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]
    r = httpx.post(f"{OPENAI_COMPAT_URL}/completions", json={
        "model":OPENAI_COMPAT_MODEL,"prompt":p,
        "max_tokens":MAX_TOKENS,"temperature":TEMPERATURE},timeout=180)
    r.raise_for_status(); return r.json()["choices"][0]["text"]

def _transformers(p):
    from functools import lru_cache
    @lru_cache(maxsize=1)
    def _load():
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        tok = AutoTokenizer.from_pretrained(HF_MODEL_ID,trust_remote_code=True)
        mdl = AutoModelForCausalLM.from_pretrained(HF_MODEL_ID,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",trust_remote_code=True)
        return tok,mdl
    tok,mdl = _load(); import torch
    text = tok.apply_chat_template([{"role":"user","content":p}],
        tokenize=False,add_generation_prompt=True) \
        if (hasattr(tok,"apply_chat_template") and tok.chat_template) else p
    inp = tok(text,return_tensors="pt").to(mdl.device)
    with torch.no_grad():
        out = mdl.generate(**inp,max_new_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,do_sample=TEMPERATURE>0,pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][inp["input_ids"].shape[1]:],skip_special_tokens=True)

def _gemini(p):
    from llm.gemini import generate_code_with_gemini
    return generate_code_with_gemini(p)

# Mock samples
_MOCK = {
    "python": '''from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import hashlib, secrets, jwt

@dataclass
class User:
    id: int; email: str; _password_hash: str
    def verify_password(self, plain: str) -> bool:
        return hashlib.sha256(plain.encode()).hexdigest() == self._password_hash

class AuthServer:
    SECRET = "change-in-prod"; ACCESS_TTL = 900
    def __init__(self, db, store): self._db=db; self._store=store
    def login(self, email: str, password: str) -> Optional[dict]:
        user = self._db.find_by_email(email)
        if not user or not user.verify_password(password): return None
        refresh = secrets.token_hex(40)
        self._store.save(refresh, user.id)
        return {"access_token": jwt.encode({"sub":user.id}, self.SECRET), "refresh_token": refresh}

class TokenStore:
    def __init__(self): self._tokens = {}
    def save(self, token, user_id): self._tokens[token] = user_id
    def get(self, token): return self._tokens.get(token)''',
    "typescript": '''import bcrypt from "bcrypt";
import jwt from "jsonwebtoken";
import crypto from "crypto";

class User {
  constructor(public id: number, public email: string, private hash: string) {}
  async verify(plain: string): Promise<boolean> { return bcrypt.compare(plain, this.hash); }
}

class AuthServer {
  constructor(private db: any, private store: any, private secret: string) {}
  async login(email: string, pw: string): Promise<{accessToken:string;refreshToken:string}|null> {
    const user = await this.db.findByEmail(email);
    if (!user || !(await user.verify(pw))) return null;
    const accessToken = jwt.sign({sub:user.id}, this.secret, {expiresIn:900});
    const refreshToken = crypto.randomBytes(40).toString("hex");
    await this.store.save(refreshToken, user.id);
    return { accessToken, refreshToken };
  }
}''',
    "java": '''package com.example.auth;
import java.util.Optional; import java.util.UUID;

public record User(long id, String email, String hash) {
  public boolean verify(String plain) { return BCrypt.checkpw(plain, hash); }
}

public class AuthServer {
  private final Database db; private final TokenStore store; private final String secret;
  public AuthServer(Database db, TokenStore store, String secret) {
    this.db=db; this.store=store; this.secret=secret;
  }
  public Optional<LoginResult> login(String email, String pw) {
    return db.findByEmail(email).filter(u->u.verify(pw)).map(user->{
      String access = issueJwt(user); String refresh = UUID.randomUUID().toString();
      store.save(refresh, user.id()); return new LoginResult(access, refresh);
    });
  }
  private String issueJwt(User u) { return Jwts.builder().subject(String.valueOf(u.id())).compact(); }
}''',
}

def generate_code(plantuml_code: str, diagram_type: str, language: str) -> dict:
    if language not in SUPPORTED_LANGUAGES:
        return {"code":f"# Language '{language}' not supported.","language":language,"error":"unsupported"}
    prompt = build_prompt(plantuml_code, diagram_type, language)
    error = None
    try:
        dispatch = {"ollama":_ollama,"openai_compat":_openai_compat,
                    "transformers":_transformers,"gemini":_gemini,
                    "mock": lambda p: _MOCK.get(language,_MOCK["python"])}
        fn = dispatch.get(BACKEND)
        if not fn: raise ValueError(f"Unknown backend: {BACKEND}")
        code = clean(fn(prompt))
        if not code: raise ValueError("Empty output")
    except Exception as e:
        logger.error("Code gen failed: %s", e)
        error = str(e)
        code = f"# Code generation failed: {e}\n# Check your model and try again."
    return {"code":code,"language":language,"error":error}
