import pytest

from copilot.domain.citation import MIN_QUOTE_CHARS, normalize, quote_is_in

SOURCE = "1. Confirmar a posição dos disjuntores em ambas as extremidades da linha."


def test_exact_quote_is_accepted():
    assert quote_is_in("Confirmar a posição dos disjuntores", SOURCE)


def test_case_and_whitespace_are_ignored():
    assert quote_is_in("CONFIRMAR   a posição\n dos disjuntores", SOURCE)


def test_accent_difference_is_rejected():
    assert not quote_is_in("Confirmar a posicao dos disjuntores", SOURCE)


def test_paraphrase_is_rejected():
    assert not quote_is_in("Verificar onde estão os disjuntores nas duas pontas", SOURCE)


def test_quote_not_in_source_is_rejected():
    assert not quote_is_in("Religar a linha imediatamente", SOURCE)


def test_too_short_quote_is_rejected_even_if_it_matches():
    short = "linha"
    assert len(short) < MIN_QUOTE_CHARS
    assert short in SOURCE
    assert not quote_is_in(short, SOURCE)


@pytest.mark.parametrize("quote", ["", "   ", "\n"])
def test_empty_quote_is_rejected(quote):
    assert not quote_is_in(quote, SOURCE)


def test_normalize_collapses_whitespace_and_case():
    assert normalize("  A\tB \n C ") == "a b c"
