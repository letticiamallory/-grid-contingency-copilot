"""Politica de conteudo (ADR-007) imposta como teste: falha se faltar marcador de ficcao."""

import re
from pathlib import Path

import pytest

from copilot.domain.procedures import parse_procedure

KB = Path(__file__).resolve().parents[2] / "knowledge_base"
FILES = sorted(KB.glob("PO-FICT-*.md"))
MAX_CHUNK_WORDS = 200


def test_knowledge_base_has_minimum_content():
    procs = [parse_procedure(f.read_text(encoding="utf-8")) for f in FILES]
    assert len(procs) >= 10
    assert any(p.status == "revogado" for p in procs)
    codes = [p.code for p in procs]
    assert len(codes) == len(set(codes)), "codigos duplicados"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_procedure_has_fiction_markers(path: Path):
    raw = path.read_text(encoding="utf-8")
    proc = parse_procedure(raw)
    assert re.fullmatch(r"PO-FICT-\d{3}", proc.code)
    assert path.name.startswith(proc.code)
    assert proc.ficticio is True
    assert "fictício" in raw.split("\n## ")[0].lower(), "aviso de ficcao ausente no cabecalho"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_chunks_are_small_and_have_actions(path: Path):
    proc = parse_procedure(path.read_text(encoding="utf-8"))
    assert proc.chunks
    for chunk in proc.chunks:
        assert len(chunk.text.split()) <= MAX_CHUNK_WORDS, chunk.section
    assert any(re.search(r"^\d+\. ", c.text, re.MULTILINE) for c in proc.chunks)
