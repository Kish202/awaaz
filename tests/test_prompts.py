import re

from lowres_asr.prompts import build_bank
from lowres_asr.prompts.bank import CATEGORY_LABELS

DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def test_bank_is_large_and_unique():
    bank = build_bank()
    assert len(bank) >= 1000
    ens = [s.en.lower() for s in bank]
    assert len(set(ens)) == len(ens)
    kinds = {s.kind for s in bank}
    assert kinds == {"question", "translate", "word"}


def test_every_prompt_has_english_and_hindi():
    for s in build_bank():
        assert s.en.strip() and s.hi.strip(), s
        assert DEVANAGARI.search(s.hi), f"Hindi text has no Devanagari: {s.hi!r}"
        assert not DEVANAGARI.search(s.en), f"English text contains Devanagari: {s.en!r}"
        assert s.category in CATEGORY_LABELS, s.category


def test_each_kind_has_a_sensible_share():
    bank = build_bank()
    n = {k: sum(1 for s in bank if s.kind == k) for k in ("question", "translate", "word")}
    assert n["question"] >= 150
    assert n["translate"] >= 250
    assert n["word"] >= 500
