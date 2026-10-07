import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, Loader2, Mic, RotateCcw, Send, Shuffle, Square, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, waitForRecording } from '@/lib/api'
import { byCode } from '@/lib/languages'
import { useRecorder } from '@/lib/useRecorder'
import { cn } from '@/lib/utils'
import Panel from './Panel'
import ErrorNote from './ErrorNote'

const MAX_SECONDS = 60
const PROMPT_LANG_KEY = 'awaaz.promptLang'

const KINDS = [
  ['', 'Mixed'],
  ['word', 'Words'],
  ['translate', 'Phrases'],
  ['question', 'Questions'],
]

const KIND_HINT = {
  word: 'One or two words is a perfect answer.',
  translate: 'Say it the way you would at home. There is no single right answer.',
  question: 'Answer in a few sentences, as if talking to a friend. Longer is better here.',
}

const REJECT_LABELS = {
  too_short: 'the clip was too short',
  too_long: `the clip was over ${MAX_SECONDS} seconds`,
  silent: 'we could not hear anything',
  undecodable: 'the audio could not be read',
}

/**
 * Conversational elicitation. The bot asks in English/Hindi; the contributor answers in
 * Gojri/Pahari by typing, recording, or both. Each answer is a `response` on the server;
 * voice goes through the same worker as read-aloud clips.
 */
export default function Talk({ lang, contributor, onAnswered }) {
  const l = byCode(lang)
  const [promptLang, setPromptLang] = useState(() => localStorage.getItem(PROMPT_LANG_KEY) || 'both')
  const [kind, setKind] = useState('')
  const [category, setCategory] = useState('')
  const [categories, setCategories] = useState([])
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [exhausted, setExhausted] = useState(false)
  const [error, setError] = useState(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [thread, setThread] = useState([]) // past exchanges, oldest first
  const [session, setSession] = useState({ answers: 0, voice: 0 })
  const rec = useRecorder({ maxSeconds: MAX_SECONDS })
  const threadEnd = useRef(null)

  useEffect(() => {
    localStorage.setItem(PROMPT_LANG_KEY, promptLang)
  }, [promptLang])

  useEffect(() => {
    api.promptCategories().then(setCategories).catch(() => setCategories([]))
  }, [])

  const refill = useCallback(async () => {
    setLoading(true)
    setError(null)
    setExhausted(false)
    try {
      const next = await api.nextPrompts(lang, contributor.id, { category: category || undefined, kind: kind || undefined })
      setQueue(next)
    } catch (e) {
      setQueue([])
      if (e.status === 404) setExhausted(true)
      else setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [lang, contributor.id, category, kind])

  useEffect(() => {
    refill()
  }, [refill])

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [thread.length])

  const current = queue[0]
  const canSend = !!current && !sending && !rec.recording && (text.trim().length > 0 || !!rec.blob)

  function advance() {
    setText('')
    rec.reset()
    setQueue((q) => {
      const rest = q.slice(1)
      if (rest.length === 0) refill()
      return rest
    })
  }

  function skip() {
    if (!current) return
    advance()
  }

  async function send() {
    if (!canSend) return
    setSending(true)
    setError(null)
    const prompt = current
    const answerText = text.trim()
    const file = rec.file()
    // Own URL for the transcript: the recorder's is revoked on reset().
    const audioUrl = file ? URL.createObjectURL(file) : null
    try {
      const res = await api.submitResponse(contributor.id, prompt.id, lang, { text: answerText || undefined, file })
      const entry = {
        id: res.id,
        prompt,
        text: res.text,
        audioUrl,
        addedToPool: res.added_to_pool,
        poolReason: res.pool_reason,
        recording: res.recording ? { id: res.recording.id, status: 'checking' } : null,
      }
      setThread((t) => [...t, entry])
      setSession((s) => ({ answers: s.answers + 1, voice: s.voice + (file ? 1 : 0) }))
      onAnswered?.()
      advance()
      if (res.recording) {
        waitForRecording(res.recording.id)
          .then((settled) =>
            setThread((t) =>
              t.map((e) =>
                e.id === res.id
                  ? { ...e, recording: { id: settled.id, status: settled.status, reason: settled.reject_reason } }
                  : e,
              ),
            ),
          )
          .catch(() => {})
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <Panel
        eyebrow={`Talk · ${l.name}`}
        title="awaaz asks, you answer"
        description={`Read the question, then reply in ${l.name}: type it, say it, or both. Nobody is grading you. The way you actually speak is exactly what we need.`}
        action={
          <div className="flex shrink-0 rounded-full border border-border/80 bg-card/60 p-0.5 text-xs" role="group" aria-label="Question language">
            {[
              ['both', 'Both'],
              ['en', 'English'],
              ['hi', 'हिन्दी'],
            ].map(([v, label]) => (
              <button
                key={v}
                onClick={() => setPromptLang(v)}
                className={cn(
                  'whitespace-nowrap rounded-full px-2.5 py-1 transition-colors',
                  v === 'hi' && 'font-devanagari',
                  promptLang === v ? 'bg-accent text-gold-soft' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        }
      >
        {/* transcript */}
        <div className="max-h-[26rem] space-y-4 overflow-y-auto pe-1" aria-live="polite">
          {thread.length === 0 && !current && !loading && (
            <p className="text-sm text-muted-foreground">Nothing to ask yet.</p>
          )}
          {thread.map((e) => (
            <Exchange key={e.id} entry={e} promptLang={promptLang} />
          ))}

          {current ? (
            <BotBubble prompt={current} promptLang={promptLang} categories={categories} live />
          ) : loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Thinking of a question…
            </div>
          ) : exhausted ? (
            <BotNote>
              You have answered everything in this topic for {l.name}. Pick another topic, or switch to Listen and
              review other people's clips.
            </BotNote>
          ) : null}
          <div ref={threadEnd} />
        </div>

        {/* composer */}
        <div className="mt-5 rounded-xl border border-gold/20 bg-gradient-to-b from-gold/[0.05] to-transparent p-4">
          <Textarea
            dir="rtl"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={!current || sending}
            placeholder={`اپنا جواب ${l.native} میں لکھیں…`}
            className="font-nastaliq min-h-20 border-0 bg-transparent px-1 text-xl text-ivory placeholder:text-muted-foreground/50 focus-visible:ring-0 md:text-xl"
          />

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={rec.toggle}
              disabled={!current || sending}
              aria-pressed={rec.recording}
              aria-label={rec.recording ? 'Stop recording' : 'Record your answer'}
              className={cn(
                'relative grid size-12 shrink-0 place-items-center rounded-full border transition-all disabled:opacity-40',
                rec.recording
                  ? 'border-destructive/50 bg-destructive/15 text-destructive'
                  : 'border-gold/40 bg-gradient-to-b from-card to-background text-gold hover:border-gold/70',
              )}
            >
              {rec.recording && <span className="absolute inset-0 animate-ping rounded-full border border-destructive/40" />}
              {rec.recording ? <Square className="size-4 fill-current" /> : <Mic className="size-5" />}
            </button>

            <div className="min-w-0 flex-1 text-sm text-muted-foreground">
              {rec.recording ? (
                <span className="tabular-nums">{rec.elapsed.toFixed(1)}s · tap to stop · up to {MAX_SECONDS}s</span>
              ) : rec.url ? (
                <div className="flex items-center gap-2">
                  <audio controls src={rec.url} className="h-8 max-w-xs opacity-80" />
                  <Button variant="ghost" size="xs" onClick={rec.reset} className="text-muted-foreground">
                    <RotateCcw /> Re-record
                  </Button>
                </div>
              ) : (
                <span>{current ? KIND_HINT[current.kind] : ''}</span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={skip} disabled={!current || sending} className="gap-1.5 text-muted-foreground">
                <Shuffle className="size-4" /> Another question
              </Button>
              <Button onClick={send} disabled={!canSend} className="gap-2">
                {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                Send
              </Button>
            </div>
          </div>
          {rec.error === 'denied' && (
            <ErrorNote className="mt-3">Microphone access was denied. Allow the microphone in your browser, or just type.</ErrorNote>
          )}
          {error && <ErrorNote className="mt-3">{error}</ErrorNote>}
        </div>
      </Panel>

      <Panel eyebrow="Choose what to talk about" title={contributor.display_name ? `Your turn, ${contributor.display_name}` : 'Your turn'}>
        <div className="space-y-5">
          <div>
            <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Kind of question</p>
            <div className="flex flex-wrap gap-1.5">
              {KINDS.map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setKind(v)}
                  className={cn(
                    'rounded-full border px-3 py-1 text-xs transition-colors',
                    kind === v
                      ? 'border-gold/50 bg-gold/10 text-gold-soft'
                      : 'border-border/80 text-muted-foreground hover:border-gold/30 hover:text-foreground',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {kind === 'word'
                ? 'Quick vocabulary: "What do you call …?"'
                : kind === 'translate'
                  ? 'Short everyday sentences to say in your own words.'
                  : kind === 'question'
                    ? 'Open questions about your life, village and memories.'
                    : 'A mix of words, phrases and open questions.'}
            </p>
          </div>

          <div>
            <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Topic</p>
            <Select value={category || 'any'} onValueChange={(v) => setCategory(v === 'any' ? '' : v)}>
              <SelectTrigger className="w-full border-border/80 bg-card/60">
                <SelectValue placeholder="Any topic" />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                <SelectItem value="any">Any topic</SelectItem>
                {categories.map((c) => (
                  <SelectItem key={c.key} value={c.key}>
                    <span>{c.label_en}</span>
                    <span className="font-devanagari ms-2 text-muted-foreground">{c.label_hi}</span>
                    <span className="ms-2 text-xs text-muted-foreground/70">{c.prompts}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border/80 bg-border/60">
            <Stat label="Answered" value={session.answers} />
            <Stat label="With voice" value={session.voice} />
          </dl>

          <ul className="space-y-3 text-sm text-muted-foreground">
            <Tip>Answer in {l.name}, not in Hindi or Urdu. Mixing in a borrowed word is fine; that is how people talk.</Tip>
            <Tip>Typing and speaking the same answer is the most valuable: the text becomes a transcript for your voice.</Tip>
            <Tip>Voice-only answers are kept as spontaneous speech and transcribed later by the community.</Tip>
            <Tip>Short typed answers are added to the pool that others read aloud in Speak.</Tip>
            <Tip>
              <kbd className="rounded border border-border/80 px-1 font-mono text-[11px]">⌘/Ctrl</kbd> +{' '}
              <kbd className="rounded border border-border/80 px-1 font-mono text-[11px]">Enter</kbd> sends.
            </Tip>
          </ul>
        </div>
      </Panel>
    </div>
  )
}

function BotBubble({ prompt, promptLang, categories, live }) {
  const cat = categories.find((c) => c.key === prompt.category)
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          <span className="text-gold/80">awaaz</span>
          {cat && (
            <>
              <span>·</span>
              <span>{cat.label_en}</span>
            </>
          )}
        </div>
        <div
          className={cn(
            'rounded-2xl rounded-tl-sm border px-4 py-3',
            live ? 'border-gold/25 bg-gold/[0.06]' : 'border-border/60 bg-card/40',
          )}
        >
          {(promptLang === 'both' || promptLang === 'en') && (
            <p className={cn('leading-relaxed', live ? 'text-lg text-ivory' : 'text-sm text-foreground/90')}>{prompt.text_en}</p>
          )}
          {(promptLang === 'both' || promptLang === 'hi') && (
            <p
              className={cn(
                'font-devanagari',
                live ? 'text-lg text-ivory' : 'text-sm text-foreground/90',
                promptLang === 'both' && 'mt-1.5 text-muted-foreground',
                promptLang === 'both' && live && 'text-base',
              )}
            >
              {prompt.text_hi}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function Exchange({ entry, promptLang }) {
  const r = entry.recording
  const note = (() => {
    const parts = []
    if (entry.text) {
      parts.push(entry.addedToPool ? 'Saved, and added to the read-aloud pool.' : 'Saved.')
    }
    if (r) {
      if (r.status === 'checking' || r.status === 'uploaded' || r.status === 'processing') parts.push('Checking your audio…')
      else if (r.status === 'ready' || r.status === 'validated') parts.push('Audio accepted; another contributor will review it.')
      else parts.push(`Audio not kept: ${REJECT_LABELS[r.reason] ?? r.reason ?? r.status}.`)
    }
    return parts.join(' ')
  })()
  const audioBad = r && !['checking', 'uploaded', 'processing', 'ready', 'validated'].includes(r.status)

  return (
    <div className="space-y-3">
      <BotBubble prompt={entry.prompt} promptLang={promptLang} categories={[]} />
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-border/60 bg-background/60 px-4 py-3">
          {entry.text && (
            <p dir="rtl" className="font-nastaliq text-xl text-ivory">
              {entry.text}
            </p>
          )}
          {entry.audioUrl && <audio controls src={entry.audioUrl} className={cn('h-8 max-w-full opacity-80', entry.text && 'mt-2')} />}
        </div>
      </div>
      <div className="flex items-center gap-2 ps-11 text-xs">
        {r && (r.status === 'checking' || r.status === 'uploaded' || r.status === 'processing') ? (
          <Loader2 className="size-3 animate-spin text-muted-foreground" />
        ) : audioBad ? (
          <X className="size-3 text-destructive" />
        ) : (
          <Check className="size-3 text-gold" />
        )}
        <span className={cn(audioBad ? 'text-destructive' : 'text-muted-foreground')}>{note}</span>
      </div>
    </div>
  )
}

function BotNote({ children }) {
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="rounded-2xl rounded-tl-sm border border-border/60 bg-card/40 px-4 py-3 text-sm text-muted-foreground">{children}</div>
    </div>
  )
}

function Avatar() {
  return (
    <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full border border-gold/30 bg-gold/10 font-display text-sm lowercase text-gold">
      a
    </span>
  )
}

function Stat({ label, value }) {
  return (
    <div className="bg-card/80 px-4 py-4">
      <dt className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-display text-3xl lining-nums tabular-nums text-foreground">{value}</dd>
    </div>
  )
}

function Tip({ children }) {
  return (
    <li className="flex gap-2.5">
      <span className="mt-2 size-1 shrink-0 rounded-full bg-gold/60" />
      <span>{children}</span>
    </li>
  )
}
