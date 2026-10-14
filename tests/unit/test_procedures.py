import pytest

from copilot.domain.procedures import ProcedureFormatError, parse_procedure

SAMPLE = """---
code: PO-FICT-900
title: Exemplo
version: "1.0"
status: vigente
ficticio: true
applies_to: [evento_x]
---

> Conteúdo fictício. Não usar em operação real.

## 1. Objetivo
Texto do objetivo.

## 4. Ações

### 4.1 Verificações
1. Primeiro passo.
2. Segundo passo.

### 4.2 Contenção
3. Terceiro passo.
"""


def test_parses_metadata_and_hash():
    proc = parse_procedure(SAMPLE)
    assert proc.code == "PO-FICT-900"
    assert proc.status == "vigente"
    assert proc.ficticio is True
    assert proc.rascunho_assistido is False
    assert proc.applies_to == ("evento_x",)
    assert len(proc.content_hash) == 64


def test_splits_by_section_and_subsection_and_drops_warning():
    proc = parse_procedure(SAMPLE)
    labels = [c.section for c in proc.chunks]
    assert labels == ["1. Objetivo", "4. Ações > 4.1 Verificações", "4. Ações > 4.2 Contenção"]
    assert all("Conteúdo fictício" not in c.text for c in proc.chunks)
    assert proc.chunks[1].text == "1. Primeiro passo.\n2. Segundo passo."


def test_crlf_gives_same_hash_as_lf():
    assert (
        parse_procedure(SAMPLE.replace("\n", "\r\n")).content_hash
        == parse_procedure(SAMPLE).content_hash
    )


def test_rejects_missing_front_matter():
    with pytest.raises(ProcedureFormatError, match="front-matter"):
        parse_procedure("## 1. Objetivo\nsem front-matter")


def test_rejects_missing_fields_and_bad_status():
    with pytest.raises(ProcedureFormatError, match="ausentes"):
        parse_procedure("---\ncode: PO-FICT-1\n---\ncorpo")
    with pytest.raises(ProcedureFormatError, match="status"):
        parse_procedure(SAMPLE.replace("status: vigente", "status: rascunho"))
