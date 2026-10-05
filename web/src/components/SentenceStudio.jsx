import { useMemo, useRef, useState } from 'react'
import { Check, Copy, Download, FileUp, Loader2, Mic, Sparkles, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { api } from '@/lib/api'
import { REASON_LABELS, byCode } from '@/lib/languages'
import { cn } from '@/lib/utils'
import Panel from './Panel'
import ErrorNote from './ErrorNote'

const SAMPLE = `میں گھر جا رہا ہوں۔ تم کہاں ہو؟ میرے پاس ۱۲ کتابیں ہیں۔ یہ hello والا جملہ ہے۔
یہ ایک لمبا
جملہ ہے۔ ميں گھر جا رہا ہوں۔ آج موسم اچھا ہے!`

export default function SentenceStudio({ lang, contributor, onContributed }) {
  const l = byCode(lang)
  const [text, setText] = useState('')
  const [source, setSource] = useState('pasted')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [poolState, setPoolState] = useState(null) // null | 'sending' | 'queued' | 'error'
  const fileRef = useRef(null)

  async function addToPool() {
    if (!result?.accepted.length) return
    setPoolState('sending')
    try {
      await api.contributeSentences(
        lang,
        result.accepted.map((a) => a.sentence),
        source,
        contributor?.id ?? null,
      )
      setPoolState('queued')
      onContributed?.()
    } catch (e) {
      setPoolState('error')
      setError(e.message)
    }
  }

  const total = result ? result.accepted.length + result.rejected.length + result.duplicates : 0
  const acceptRate = total ? Math.round((result.accepted.length / total) * 100) : 0

  async function run(input = text, src = source) {
    if (!input.trim()) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.splitSentences(lang, input, src))
      setPoolState(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function onFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const content = await file.text()
    setText(content)
    setSource(file.name)
    run(content, file.name)
    e.target.value = ''
  }

  function download() {
    const blob = new Blob([result.accepted.map((a) => a.sentence).join('\n') + '\n'], {
      type: 'text/plain;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const a = Object.assign(document.createElement('a'), { href: url, download: `${lang}-sentences.txt` })
    a.click()
    URL.revokeObjectURL(url)
  }

  async function copy() {
    await navigator.clipboard.writeText(result.accepted.map((a) => a.sentence).join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  const reasons = useMemo(
    () => (result ? Object.entries(result.reasons).sort((a, b) => b[1] - a[1]) : []),
    [result],
  )

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <Panel
        eyebrow="Source text"
        title="Paste or upload"
        description={`Books, folk tales, transcripts. Sentences are split, normalised to Urdu-script conventions and checked against Common Voice rules (${l.name}: 2–14 words).`}
      >
        <Textarea
          dir="rtl"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="یہاں متن چسپاں کریں…"
          className="font-nastaliq min-h-72 resize-y bg-background/50 text-[17px] leading-[2.2] placeholder:text-muted-foreground/50 focus-visible:ring-gold/40"
        />
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={() => run()} disabled={busy || !text.trim()} className="gap-2">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            Extract sentences
          </Button>
          <Button variant="outline" onClick={() => fileRef.current?.click()} className="gap-2">
            <FileUp className="size-4" /> Upload .txt
          </Button>
          <input ref={fileRef} type="file" accept=".txt,.md,text/plain" hidden onChange={onFile} />
          <Button
            variant="ghost"
            className="ms-auto text-muted-foreground"
            onClick={() => {
              setText(SAMPLE)
              setSource('sample')
              run(SAMPLE, 'sample')
            }}
          >
            Try a sample
          </Button>
        </div>
        {error && <ErrorNote className="mt-4">{error}</ErrorNote>}
      </Panel>

      <Panel
        eyebrow="Result"
        title={result ? `${result.accepted.length} ready to record` : 'Nothing extracted yet'}
        description={
          result
            ? `${result.rejected.length} rejected · ${result.duplicates} duplicates folded · ${acceptRate}% acceptance`
            : 'Accepted sentences appear here with provenance; rejections carry a reason so the source can be fixed.'
        }
        action={
          result &&
          result.accepted.length > 0 && (
            <div className="flex gap-1">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="icon" variant="ghost" onClick={copy} aria-label="Copy">
                    {copied ? <Check className="size-4 text-gold" /> : <Copy className="size-4" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Copy accepted sentences</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="icon" variant="ghost" onClick={download} aria-label="Download">
                    <Download className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Download sentences.txt</TooltipContent>
              </Tooltip>
            </div>
          )
        }
      >
        {!result ? (
          <EmptyState />
        ) : (
          <>
            <AcceptanceBar accepted={result.accepted.length} rejected={result.rejected.length} dup={result.duplicates} />
            {reasons.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {reasons.map(([r, n]) => (
                  <Badge key={r} variant="outline" className="gap-1.5 border-border/80 text-muted-foreground">
                    <span className="size-1.5 rounded-full bg-destructive/70" />
                    {REASON_LABELS[r] ?? r}
                    <span className="tabular-nums text-foreground/80">{n}</span>
                  </Badge>
                ))}
              </div>
            )}
            <div className="mt-5 flex flex-wrap items-center gap-3 rounded-lg border border-gold/20 bg-gold/[0.04] px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">Add these {result.accepted.length} sentences to the recording pool</p>
                <p className="text-xs text-muted-foreground">
                  They go through the queue, get deduplicated against what is already there, and become available for contributors to read aloud.
                </p>
              </div>
              <Button onClick={addToPool} disabled={poolState === 'sending' || poolState === 'queued'} className="gap-2">
                {poolState === 'sending' ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : poolState === 'queued' ? (
                  <Check className="size-4" />
                ) : (
                  <Mic className="size-4" />
                )}
                {poolState === 'queued' ? 'Queued' : 'Add to pool'}
              </Button>
            </div>
            <Separator className="my-5 bg-border/60" />
            <ScrollArea className="h-[26rem] pe-3">
              <ol className="space-y-2">
                {result.accepted.map((a, i) => (
                  <Row key={`a${i}`} index={i + 1} text={a.sentence} source={a.source} ok />
                ))}
                {result.rejected.map((r, i) => (
                  <Row key={`r${i}`} text={r.sentence} source={r.source} reason={REASON_LABELS[r.reason] ?? r.reason} />
                ))}
              </ol>
            </ScrollArea>
          </>
        )}
      </Panel>
    </div>
  )
}

function Row({ index, text, source, reason, ok }) {
  return (
    <li
      className={cn(
        'group grid grid-cols-[2rem_minmax(0,1fr)] items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors',
        ok
          ? 'border-border/60 bg-background/40 hover:border-gold/30'
          : 'border-destructive/15 bg-destructive/[0.04] hover:border-destructive/30',
      )}
    >
      <span className="mt-1.5 flex justify-center">
        {ok ? (
          <span className="font-display text-sm tabular-nums text-gold/80">{String(index).padStart(2, '0')}</span>
        ) : (
          <X className="size-3.5 text-destructive/80" />
        )}
      </span>
      <div className="min-w-0">
        <p dir="rtl" className="font-nastaliq text-[16px] text-foreground/95">
          {text}
        </p>
        <p className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
          {reason && <span className="text-destructive/90">{reason}</span>}
          {reason && <span aria-hidden>·</span>}
          <span className="truncate">{source}</span>
        </p>
      </div>
    </li>
  )
}

function AcceptanceBar({ accepted, rejected, dup }) {
  const total = accepted + rejected + dup || 1
  const seg = (n) => `${(n / total) * 100}%`
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <span className="bg-gradient-to-r from-gold to-gold-soft" style={{ width: seg(accepted) }} />
      <span className="bg-muted-foreground/40" style={{ width: seg(dup) }} />
      <span className="bg-destructive/60" style={{ width: seg(rejected) }} />
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex h-[26rem] flex-col items-center justify-center rounded-lg border border-dashed border-border/70 text-center">
      <p dir="rtl" className="font-nastaliq text-2xl text-muted-foreground/40">
        ایک ایک جملہ
      </p>
      <p className="mt-2 text-sm text-muted-foreground">One sentence at a time.</p>
    </div>
  )
}
