"""
rag/prompt_builder.py
---------------------
Builds the final prompt that is sent to the local LLM.

Design goals:
- Inject retrieved UML rules and examples as context.
- Instruct the model to output ONLY valid PlantUML, nothing else.
- Keep prompt within a token budget so small models don't choke.
"""

from __future__ import annotations

from rag.retriever import RetrievedChunk

# Max characters of context we inject (roughly 700 tokens for a 7B model)
CONTEXT_CHAR_LIMIT = 3500

SYSTEM_PROMPT = """\
You are a UML diagram code generator. Your ONLY job is to write valid PlantUML code.

Rules you MUST follow:
1. Output ONLY the PlantUML code block. Start with @startuml and end with @enduml.
2. Do NOT output any explanation, comments outside the block, or markdown fences.
3. Follow the syntax rules in the CONTEXT section exactly.
4. Use the examples in the CONTEXT section as style references.
5. If you are unsure about a detail, make a reasonable assumption and keep the diagram valid.
6. Never include placeholder text like "..." unless it is inside a note.
"""


def build_prompt(
    description: str,
    diagram_type: str,
    chunks: list[RetrievedChunk],
) -> str:
    """
    Return the full prompt string to send to the LLM.

    The prompt structure is:
        <SYSTEM>
        <CONTEXT: retrieved chunks>
        <USER REQUEST>
    """
    context_parts = _select_context(chunks)
    context_block = "\n\n---\n\n".join(context_parts)

    prompt = f"""{SYSTEM_PROMPT}

=== CONTEXT (UML rules and examples) ===
{context_block}

=== USER REQUEST ===
Diagram type: {diagram_type}
Description: {description}

Generate the PlantUML code now:"""

    return prompt


def _select_context(chunks: list[RetrievedChunk]) -> list[str]:
    """
    Pick chunks greedily until we hit CONTEXT_CHAR_LIMIT.
    Prioritise rules first, then examples.
    """
    rules = [c for c in chunks if c.content_type == "rule"]
    examples = [c for c in chunks if c.content_type == "example"]
    docs = [c for c in chunks if c.content_type == "documentation"]

    ordered = rules + examples + docs  # rules first for accuracy

    selected = []
    total = 0
    for chunk in ordered:
        if total + len(chunk.text) > CONTEXT_CHAR_LIMIT:
            break
        selected.append(chunk.text)
        total += len(chunk.text)

    return selected
