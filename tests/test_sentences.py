from lowres_asr.config import SentenceConfig, TextConfig
from lowres_asr.text.sentences import SentenceFilter, extract_sentences, split_sentences

# Short Urdu-orthography sentences used as stand-ins for Gojri/Pahari text.
S1 = "میں گھر جا رہا ہوں۔"
S2 = "تم کہاں ہو؟"
S3 = "آج موسم اچھا ہے!"


def test_split_keeps_terminators_and_joins_wrapped_lines():
    text = f"{S1} {S2}\nیہ ایک لمبا\nجملہ ہے۔ {S3}"
    got = list(split_sentences(text, ["۔", "؟", "!"]))
    assert got == [S1, S2, "یہ ایک لمبا جملہ ہے۔", S3]


def test_split_handles_trailing_text_without_terminator():
    got = list(split_sentences("پہلا جملہ۔ آخری بغیر نقطہ", ["۔"]))
    assert got == ["پہلا جملہ۔", "آخری بغیر نقطہ"]


def test_filter_reasons():
    f = SentenceFilter(SentenceConfig(min_words=2, max_words=5), TextConfig())
    assert f.check(S1) is None
    assert f.check("سلام۔") == "too_short"
    assert f.check("ایک دو تین چار پانچ چھ سات۔") == "too_long"
    assert f.check("میرے پاس ۱۲ کتابیں ہیں۔") == "digits"
    assert f.check("یہ hello والا جملہ۔") == "latin"
    assert f.check("یہ देवनागरी والا جملہ۔") == "foreign_char"
    assert f.check("دیکھو www.example.com ابھی۔") == "url"
    assert f.check("ڈ۔ صاحب آئے ہیں۔") == "abbreviation"
    assert f.check("یہ بہتتت اچھا ہے۔") == "repeat_chars"


def test_extract_dedupes_on_normalised_form_and_keeps_punctuation():
    # Same sentence twice, once with Arabic-form yeh and a harakat: should dedupe.
    variant = S1.replace("\u06cc", "\u064a").replace("ہوں", "ہُوں")
    sources = [("a.txt", f"{S1} {S2}"), ("b.txt", f"{variant} {S3}")]
    res = extract_sentences(sources, SentenceConfig(), TextConfig())
    accepted = [s for s, _ in res.accepted]
    assert accepted == [S1, S2, S3]
    assert res.duplicates == 1
    assert res.rejected == []
    assert res.accepted[0][1] == "a.txt" and res.accepted[2][1] == "b.txt"


def test_extract_published_sentences_keep_diacritics():
    s = "یہ مُحَبّت ہے۔"
    res = extract_sentences([("x", s)], SentenceConfig(), TextConfig(strip_diacritics=True))
    assert res.accepted[0][0] == s


def test_summary_mentions_counts():
    res = extract_sentences([("x", f"{S1} سلام۔")], SentenceConfig(), TextConfig())
    text = res.summary()
    assert "accepted:   1" in text
    assert "too_short" in text
