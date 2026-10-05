from lowres_asr.config import TextConfig
from lowres_asr.text.normalize import char_inventory, normalize, normalize_for_asr


def test_arabic_forms_fold_to_urdu_forms():
    # Arabic yeh/kaf/heh -> Urdu farsi-yeh/keheh/heh-goal
    assert normalize("\u064a\u0643\u0647") == "\u06cc\u06a9\u06c1"


def test_presentation_forms_are_decomposed():
    # U+FEFB is the isolated LAM-ALEF ligature; NFKC should give ل + ا
    assert normalize("\ufefb") == "\u0644\u0627"


def test_tatweel_and_bidi_marks_removed():
    assert normalize("\u0633\u0640\u0640\u0644\u0627\u0645\u200f") == "\u0633\u0644\u0627\u0645"


def test_diacritics_stripped_by_default_but_kept_when_disabled():
    word = "\u0645\u064f\u062d\u064e\u0628\u0651\u062a"  # مُحَبّت with harakat + shadda
    assert normalize(word) == "\u0645\u062d\u0628\u062a"
    assert normalize(word, TextConfig(strip_diacritics=False)) == word


def test_preserve_chars_override_letter_map():
    cfg = TextConfig(preserve_chars=["\u0643"])  # keep Arabic kaf verbatim
    assert normalize("\u0643", cfg) == "\u0643"


def test_digits_modes():
    assert normalize("\u06f1\u06f2\u0663") == "123"
    assert normalize("12", TextConfig(digits="urdu")) == "\u06f1\u06f2"
    assert normalize("\u06f1", TextConfig(digits="keep")) == "\u06f1"


def test_zwnj_kept_by_default_stripped_on_request():
    s = "\u0645\u06cc\u200c\u062e\u0648\u0627\u06c1\u0645"
    assert normalize(s) == s
    assert normalize(s, TextConfig(strip_zwnj=True)) == s.replace("\u200c", "")


def test_asr_normaliser_drops_punctuation_and_collapses_space():
    s = "\u06cc\u06c1 \u06a9\u06cc\u0627 \u06c1\u06d2\u061f  \u0633\u0644\u0627\u0645\u06d4"
    assert normalize_for_asr(s) == "\u06cc\u06c1 \u06a9\u06cc\u0627 \u06c1\u06d2 \u0633\u0644\u0627\u0645"


def test_char_inventory_sorted_by_frequency():
    rows = char_inventory(["aab", "a b"])
    assert rows[0][0] == "a" and rows[0][3] == 3
    assert rows[0][1] == "U+0061"
    assert all(not r[0].isspace() for r in rows)
