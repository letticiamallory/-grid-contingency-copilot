"""Parsing of operating procedures (Markdown with YAML front-matter) into chunks.

Pure functions, no I/O: callers read files and pass the text.
"""

import hashlib
import re
from dataclasses import dataclass

import yaml

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_REQUIRED = ("code", "title", "version", "status", "ficticio", "applies_to")
_STATUSES = ("vigente", "revogado")


class ProcedureFormatError(ValueError):
    pass


@dataclass(frozen=True)
class ChunkDraft:
    section: str
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    procedure_code: str
    procedure_version: str
    section: str
    text: str
    score: float


@dataclass(frozen=True)
class Procedure:
    code: str
    title: str
    version: str
    status: str
    ficticio: bool
    rascunho_assistido: bool
    applies_to: tuple[str, ...]
    content_hash: str
    chunks: tuple[ChunkDraft, ...]


def parse_procedure(raw: str) -> Procedure:
    text = raw.replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if not match:
        raise ProcedureFormatError("front-matter ausente")
    meta = yaml.safe_load(match.group(1)) or {}
    missing = [k for k in _REQUIRED if k not in meta]
    if missing:
        raise ProcedureFormatError(f"campos obrigatorios ausentes: {', '.join(missing)}")
    if meta["status"] not in _STATUSES:
        raise ProcedureFormatError(f"status invalido: {meta['status']!r}")
    return Procedure(
        code=str(meta["code"]),
        title=str(meta["title"]),
        version=str(meta["version"]),
        status=str(meta["status"]),
        ficticio=meta["ficticio"] is True,
        rascunho_assistido=meta.get("rascunho_assistido") is True,
        applies_to=tuple(str(x) for x in meta["applies_to"]),
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        chunks=tuple(_split_chunks(text[match.end() :])),
    )


def _split_chunks(body: str) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    section = ""
    subsection = ""
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        buffer.clear()
        if content and section:
            label = f"{section} > {subsection}" if subsection else section
            chunks.append(ChunkDraft(section=label, text=content))

    for line in body.split("\n"):
        if line.startswith("### "):
            flush()
            subsection = line[4:].strip()
        elif line.startswith("## "):
            flush()
            section = line[3:].strip()
            subsection = ""
        elif line.startswith(">"):
            continue  # aviso de conteudo ficticio: nao e conteudo citavel
        else:
            buffer.append(line)
    flush()
    return chunks
