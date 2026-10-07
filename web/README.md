# awaaz — web UI

React 19 · Vite · Tailwind CSS v4 · shadcn/ui (radix, JavaScript, RTL enabled).

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
npm run build    # static bundle in dist/
```

Start the backend first from the repo root: `lowres-asr-api`.

## Design notes

- Single warm, ink-dark theme with champagne gold accents (`src/index.css`). Colours are
  oklch so the gold keeps its character against the near-black neutrals.
- Type: Cormorant Garamond for display, Geist for UI, Noto Nastaliq Urdu for all Gojri and
  Pahari text. Anything in the Perso-Arabic script uses the `font-nastaliq` utility, which
  also sets `direction: rtl` and a tall line-height Nastaliq needs.
- Custom utilities: `text-gold-gradient` (slow metallic shimmer), `border-gilt` (gradient
  hairline border), `grain` (film grain overlay), `rise` (entrance).
- `src/lib/languages.js` holds the static Common Voice 26.0 figures shown in the hero.

## Structure

```
src/
  App.jsx                    shell: header, hero, tabbed workbench, pipeline, footer
  components/
    ConsentGate.jsx          one-time CC0 + storage consent, optional name/demographics
    Talk.jsx                 "Talk": bot asks (EN/HI) -> type and/or record the answer -> next
    Contribute.jsx           "Speak": sentence -> record -> submit -> worker verdict -> next
    Listen.jsx               peer validation of other people's clips
    LiveStats.jsx            counts from the database
    Header.jsx               wordmark + language switch
    LanguageSwitch.jsx       Gojri / Pahari radio pill
    Hero.jsx, StatCard.jsx   headline and Common Voice stats
    Panel.jsx                gilt card with eyebrow/title/action
    SentenceStudio.jsx       paste/upload -> accepted + rejected sentences, copy/download
    Transcribe.jsx           record or drop audio -> transcript + normalised form
    Charset.jsx              code-point inventory, Arabic-form letters flagged
    Pipeline.jsx             the four-step loop
    ErrorNote.jsx
    ui/                      shadcn components
  lib/api.js                 fetch wrapper for the FastAPI backend
  lib/useRecorder.js         MediaRecorder hook shared by Talk and Speak
  lib/contributor.js         localStorage-backed anonymous contributor id + hook
  lib/languages.js           static language facts and rejection labels
```
