import json
from collections.abc import Sequence
from pathlib import Path
from string import Template

from copilot.domain.models import Event
from copilot.domain.procedures import RetrievedChunk

PROMPT_VERSION = "v1"
PROMPTS_DIR = Path(__file__).parent / "prompts"


def build_search_query(event: Event) -> str:
    """Free text derived from the event. The event type (English identifier) is matched through
    the procedures' `applies_to`, not through this text. The element id is left out on purpose:
    an id like "SE-FICT-01" yields the token "fict", which stem-matches "fictícia" in nearly
    every chunk and made unrelated events look covered."""
    values = " ".join(str(v) for v in event.attributes.values())
    return f"{event.type.replace('_', ' ')} {values}".strip()


def render_prompt(event: Event, chunks: Sequence[RetrievedChunk]) -> tuple[str, str]:
    """Returns (system, user)."""
    system = (PROMPTS_DIR / f"{PROMPT_VERSION}.system.md").read_text(encoding="utf-8")
    event_json = json.dumps(
        {
            "tipo": event.type,
            "elemento": event.element,
            "ocorrido_em": event.occurred_at.isoformat(),
            "atributos": event.attributes,
        },
        ensure_ascii=False,
        indent=2,
    )
    rendered_chunks = "\n\n".join(
        f"[chunk_id={c.chunk_id}] ({c.procedure_code} v{c.procedure_version}, {c.section})\n"
        f"{c.text}"
        for c in chunks
    )
    user = Template(
        (PROMPTS_DIR / f"{PROMPT_VERSION}.user.md").read_text(encoding="utf-8")
    ).substitute(event=event_json, chunks=rendered_chunks)
    return system, user
