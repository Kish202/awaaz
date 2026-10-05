# lowres-asr: Gojri and Pahari-Pothwari speech tooling

Open tooling for two Indo-Aryan languages of the Pir Panjal / Pothohar region that have
almost no speech technology: **Gojri** (`gju`, Gujjar community, J&K / Pakistan / Afghanistan)
and **Pahari-Pothwari** (`phr`, Pothohar Plateau and Azad Kashmir). Both are written in Urdu
orthography.

## Why this and not another recording app

As of Common Voice 26.0 (June 2026) the languages already have recording infrastructure:

| language | hours | speakers | sentences in corpus |
|---|---|---|---|
| Gojri `gju` | 10.7 | 7 | 3,854 |
| Pahari-Pothwari `phr` | 14.1 | 63 | 2,077 |

The bottleneck is not volunteers or software, it is **sentences**: a few thousand each, and
Common Voice will not let the same sentence be recorded indefinitely. Nobody has published
an ASR model for either language. So this repo does two things:

1. **Sentence sourcing**: turn typed-up books, OCR output and transcripts into a clean,
   deduplicated, rule-compliant sentence corpus for bulk submission to Common Voice.
2. **First ASR models**: fine-tune Whisper on the Common Voice data, report WER/CER against
   the zero-shot baseline, and publish checkpoints.

Everything is driven by one YAML config per language (`configs/gju.yaml`, `configs/phr.yaml`)
so the same orthography rules apply to the corpus, the training targets and the evaluation.

## Install

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'          # text pipeline + tests (light, no torch)
pip install -e '.[train,pdf]'    # add Whisper fine-tuning and PDF ingestion
```

## Sentence pipeline

```bash
# 1. See exactly which code points your source text uses. Stray Arabic-form letters
#    (ي ك ه) show up here; so do the language-specific letters you must preserve.
lowres-asr charset gju data/sentences/gju/raw/

# 2. Build the corpus. Accepts .txt/.md/.pdf files or directories.
lowres-asr sentences gju data/sentences/gju/raw/ --out data/sentences/gju/out
```

Output:
- `sentences.txt`: one sentence per line, ready for Common Voice bulk submission
- `sentences.tsv`: sentence + source file, for provenance / licence tracking
- `rejected.tsv`: every rejected sentence with a reason (`too_long`, `digits`, `latin`,
  `foreign_char`, `url`, `abbreviation`, `repeat_chars`) so the source can be fixed

Rules follow Common Voice's sentence guidelines (short, no digits, no foreign script, no
abbreviations) and are tunable in the `sentences:` block of the config. Dedup is on the
orthographically normalised form, so a sentence typed once with ي and once with ی counts once.

**Licensing matters.** Common Voice only accepts CC0 / public-domain sentences. Keep the
`source` column honest and get written permission from authors before submitting.

## Common Voice data

Download the `gju` or `phr` release from the
[Mozilla Data Collective](https://mozilladatacollective.com/) (free account) and extract to
`data/raw/`. Then:

```bash
lowres-asr cv-stats phr --cv-root data/raw
```

prints clips, speakers, unique sentences, gender/age skew, and train/test overlap. With 7
speakers in Gojri expect any model to overfit speaker identity; check this before believing a
WER number.

## ASR

```bash
# zero-shot baseline (Whisper conditioned on Urdu, the closest supported language)
lowres-asr evaluate phr --cv-root data/raw --model openai/whisper-small --limit 200

# fine-tune
lowres-asr train phr --cv-root data/raw --out runs/phr-whisper-small

# evaluate the fine-tuned checkpoint with a per-utterance error dump
lowres-asr evaluate phr --cv-root data/raw --model runs/phr-whisper-small/final \
    --out-tsv runs/phr-whisper-small/test_errors.tsv

# transcribe anything
lowres-asr transcribe phr --model runs/phr-whisper-small/final clip1.mp3 clip2.wav
```

Whisper has no Gojri/Pahari language token; `whisper_language: urdu` in the config tells the
decoder to start from Urdu and fine-tuning does the rest. `--max-train-samples 64 --max-steps 20`
gives a smoke test on a laptop. Real training wants a GPU (Colab/Kaggle T4 is enough for
`whisper-small` on 14 hours).

## Contribution platform ("awaaz")

`web/` is a React + Tailwind + shadcn/ui front end where people **speak** sentences,
**listen** to and validate each other's clips, and **add text** to the sentence pool. Every
contribution is stored. The backend is FastAPI + PostgreSQL + Celery/Redis + ffmpeg.

```
browser ──upload──▶ FastAPI ──row──▶ PostgreSQL
                      │ file           ▲
                      ▼                │ status, duration, accept/reject
                 Cloudinary ◀──▶ Celery worker ◀── Redis queue ◀── FastAPI (enqueue)
             (or local disk)       │ ffmpeg → 16 kHz mono WAV, silence trim, RMS
```

The API never processes audio. An upload is: store the file, insert a row with status
`uploaded`, push one job to Redis, return `202`. Workers fetch the original, convert,
measure and judge each clip, store the 16 kHz WAV next to it, then set `ready` or
`rejected`. 500 simultaneous uploads are 500 small object writes and 500 Redis pushes;
add workers to drain faster.

Audio lives in **Cloudinary** in production (`STORAGE_BACKEND=cloudinary`,
`CLOUDINARY_URL=cloudinary://key:secret@cloud`). Originals and WAVs are stored as
`video` resources (Cloudinary's type for audio) at `<CLOUDINARY_FOLDER>/<lang>/<yyyy>/<mm>/<id>`,
the validation UI streams clips straight from the Cloudinary CDN, and the training export
emits Cloudinary URLs. API and worker therefore share nothing but PostgreSQL and Cloudinary
and can run on separate hosts. For development `STORAGE_BACKEND=local` writes under
`STORAGE_DIR` instead.

### Consent and anonymity

Contributors are anonymous by default. Before the first recording they must tick two
boxes: CC0 release of their recordings and sentences, and consent to storage/publication of
their voice. Both are stored as timestamps with a consent version. A display name is
optional. Age band, gender and district are optional and self-reported. The browser keeps
only a random server-issued UUID in `localStorage`; "forget me on this device" removes it.

### Data model

| table | one row per |
|---|---|
| `contributors` | consenting person (anonymous unless they typed a name) |
| `sentences` | unique normalised sentence per language, with `recording_count` |
| `recordings` | one clip of one contributor reading one sentence; status machine `uploaded → processing → ready → validated / rejected` |
| `validations` | one contributor's verdict on one recording (unique pair) |

A recording becomes `validated` after `VOTES_TO_SETTLE` (default 2) "good" votes from
other contributors, or `rejected` after as many "bad" votes. `GET /api/export/{lang}.tsv`
(admin token) streams the validated `(wav_path, sentence, speaker_id, duration)` manifest for
training.

### Run it

```bash
# 1. infrastructure (or point .env at your own Postgres/Redis)
docker compose up -d                 # PostgreSQL :5432, Redis :6379
brew install ffmpeg                  # or apt install ffmpeg

# 2. backend
pip install -e '.[api]'
cp .env.example .env                 # edit DATABASE_URL, REDIS_URL, ADMIN_TOKEN; Cloudinary vars for prod
alembic upgrade head                 # create tables
lowres-asr-api                       # http://127.0.0.1:8000  (RELOAD=1 for dev)
lowres-asr-worker --concurrency=4    # Celery worker; run several on a busy server

# 3. frontend
cd web && npm install && npm run dev # http://localhost:5173 (proxies /api to :8000)
```

Schema changes: edit `src/lowres_asr/db/models.py`, then
`alembic revision --autogenerate -m "..."` and `alembic upgrade head`.

On macOS the worker uses Celery's thread pool (the default prefork pool breaks under the
`spawn` start method). Linux uses prefork. Both are fine: the work is an ffmpeg subprocess.

### Production notes

- Put the API behind a reverse proxy (Caddy/nginx) with TLS; set `CORS_ORIGINS` to your domain.
- Set `STORAGE_BACKEND=cloudinary` and `CLOUDINARY_URL` (Cloudinary console → API Keys).
  Audio counts against Cloudinary's *video* storage/bandwidth quota. Assets are public by
  URL, which matches the CC0 consent contributors give; the public IDs are random UUIDs.
- Rate limit on uploads is per IP (`RECORDING_RATE_LIMIT`, default 30/minute); uploads are
  capped at `MAX_UPLOAD_BYTES` (10 MB) and streamed, never buffered.
- Run `alembic upgrade head` as a deploy step before starting new API/worker versions.
- Transcription in the UI needs the `[train]` extra installed in the same environment as
  the API; otherwise it returns a clear 503.

## Layout

```
configs/            per-language YAML (orthography, sentence rules, training hparams)
src/lowres_asr/
  text/normalize.py Urdu-script Unicode normalisation (NFKC, letter folding, diacritics, digits)
  text/sentences.py split / filter / dedupe into Common Voice-ready sentences
  data/common_voice.py  read extracted CV releases; build HF datasets
  train/whisper.py  Seq2SeqTrainer fine-tuning
  metrics.py        WER/CER on a CV split
  transcribe.py     batch inference
  cli.py            `lowres-asr` entry point
  api.py            FastAPI app factory + stateless text endpoints
  settings.py       env/.env configuration (pydantic-settings)
  db/               SQLAlchemy models and session
  storage.py        audio storage: Cloudinary (production) or local disk (dev)
  queue/            Celery app and tasks (process_recording, ingest_sentences)
  routers/          contributors, sentences, recordings, validations, stats/export
alembic/            database migrations
tests/              unit tests for the text pipeline (no audio or torch needed)
web/                React + Tailwind + shadcn/ui front end
docker-compose.yml  PostgreSQL + Redis for dev/small prod
```

## Roadmap

- [ ] Confirm the Gojri-specific code points against the CV `gju` corpus and fill `preserve_chars`
- [ ] Baseline WER for `whisper-small` zero-shot on both test sets
- [ ] First fine-tuned checkpoints on Hugging Face
- [ ] Submit the first batch of new sentences to Common Voice
- [ ] Try `facebook/mms-1b-all` / wav2vec2-CTC as an alternative to Whisper
- [ ] Devanagari ↔ Nastaliq transliteration for Gojri (both scripts are in use in India)

## Related resources

- Common Voice datasets: [Gojri](https://mozilladatacollective.com/datasets/cmqi90sqx000vnr07ej5uxyct), [Pahari-Pothwari](https://mozilladatacollective.com/datasets/cmqi9csv20061nq07a7pzrd1w)
- [Gojri Literature Corpus](https://mozilladatacollective.com/datasets/cmlgz1vdt001omg07rv25gwnu) (~61K tokens)
- [junaidaslam/gojri-ai](https://github.com/jaslam94/gojri-ai): Gojri PDFs, OCR gold set, lexicon
- Pahari POS-tagged corpus (200K tokens), 2026
- For Dogri and Kashmiri, AI4Bharat's IndicVoices / IndicConformer / IndicTrans2 already cover ASR, TTS and MT.
