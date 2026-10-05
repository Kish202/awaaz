import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronRight, Loader2, Mic, RotateCcw, Square, UploadCloud, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api, waitForRecording } from '@/lib/api'
import { byCode } from '@/lib/languages'
import { cn } from '@/lib/utils'
import Panel from './Panel'
import ErrorNote from './ErrorNote'

const REJECT_LABELS = {
  too_short: 'Too short. Read the whole sentence.',
  too_long: 'Too long. Keep it under 15 seconds.',
  silent: 'We could not hear anything. Check your microphone.',
  undecodable: 'The audio could not be read. Try again.',
}

/**
 * Record loop: sentence -> record -> listen -> submit -> next.
 * Uploads return immediately (202) and the clip is judged by the worker; we poll
 * for a few seconds so the contributor sees "accepted" or a reason, then move on.
 */
export default function Contribute({ lang, contributor, onRecorded }) {
  const l = byCode(lang)
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [blob, setBlob] = useState(null)
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [phase, setPhase] = useState('idle') // idle | uploading | judging | accepted | rejected
  const [verdict, setVerdict] = useState(null)
  const [session, setSession] = useState({ accepted: 0, rejected: 0 })
  const recorder = useRef(null)
  const chunks = useRef([])
  const timer = useRef(null)
  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob])
  useEffect(() => () => url && URL.revokeObjectURL(url), [url])

  const current = queue[0]

  const refill = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await api.nextSentences(lang, contributor.id, 5)
      setQueue(next)
    } catch (e) {
      setQueue([])
      setError(e.status === 404 ? null : e.message)
    } finally {
      setLoading(false)
    }
  }, [lang, contributor.id])

  useEffect(() => {
    refill()
  }, [refill])

  function reset() {
    setBlob(null)
    setPhase('idle')
    setVerdict(null)
    setElapsed(0)
  }

  async function toggleRecord() {
    if (recording) {
      recorder.current?.stop()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      })
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((m) => MediaRecorder.isTypeSupported(m))
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      chunks.current = []
      rec.ondataavailable = (e) => chunks.current.push(e.data)
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        clearInterval(timer.current)
        setBlob(new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' }))
        setRecording(false)
      }
      rec.start()
      recorder.current = rec
      setRecording(true)
      setElapsed(0)
      const t0 = Date.now()
      timer.current = setInterval(() => {
        const s = (Date.now() - t0) / 1000
        setElapsed(s)
        if (s >= 15) rec.stop()
      }, 100)
    } catch {
      setError('Microphone access was denied. Allow the microphone in your browser and try again.')
    }
  }

  async function submit() {
    if (!blob || !current) return
    setPhase('uploading')
    setError(null)
    try {
      const ext = blob.type.includes('mp4') ? 'm4a' : 'webm'
      const file = new File([blob], `clip.${ext}`, { type: blob.type })
      const rec = await api.uploadRecording(contributor.id, current.id, file)
      setPhase('judging')
      const settled = await waitForRecording(rec.id)
      if (settled.status === 'ready' || settled.status === 'validated') {
        setPhase('accepted')
        setSession((s) => ({ ...s, accepted: s.accepted + 1 }))
      } else {
        setPhase('rejected')
        setVerdict(settled.reject_reason ?? settled.status)
        setSession((s) => ({ ...s, rejected: s.rejected + 1 }))
      }
      onRecorded?.()
    } catch (e) {
      setPhase('idle')
      setError(e.message)
    }
  }

  function next() {
    reset()
    setQueue((q) => {
      const rest = q.slice(1)
      if (rest.length === 0) refill()
      return rest
    })
  }

  function skip() {
    reset()
    setQueue((q) => [...q.slice(1), q[0]].filter(Boolean))
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <Panel
        eyebrow={`Read aloud · ${l.name}`}
        title={current ? 'Read this sentence' : loading ? 'Loading…' : 'Nothing left to read'}
        description={
          current
            ? 'Speak naturally, at your usual pace. One sentence, one clip. If you stumble, record again.'
            : loading
              ? ''
              : `You have recorded every approved ${l.name} sentence. Add more text in the Sentence studio, or go validate other people's clips.`
        }
        action={
          current && (
            <Badge variant="outline" className="border-border/80 text-muted-foreground">
              {current.recording_count} {current.recording_count === 1 ? 'voice' : 'voices'} so far
            </Badge>
          )
        }
      >
        {current ? (
          <>
            <div
              dir="rtl"
              className="font-nastaliq flex min-h-40 items-center justify-center rounded-xl border border-gold/20 bg-gradient-to-b from-gold/[0.06] to-transparent px-8 py-6 text-center text-3xl text-ivory sm:text-4xl"
            >
              {current.text}
            </div>

            <div className="mt-6 flex flex-col items-center gap-4">
              <button
                onClick={toggleRecord}
                disabled={phase === 'uploading' || phase === 'judging' || phase === 'accepted'}
                aria-pressed={recording}
                aria-label={recording ? 'Stop recording' : 'Start recording'}
                className={cn(
                  'relative grid size-24 place-items-center rounded-full border transition-all disabled:opacity-40',
                  recording
                    ? 'border-destructive/50 bg-destructive/15 text-destructive'
                    : 'border-gold/40 bg-gradient-to-b from-card to-background text-gold hover:scale-[1.03] hover:border-gold/70',
                )}
              >
                {recording && <span className="absolute inset-0 animate-ping rounded-full border border-destructive/40" />}
                {recording ? <Square className="size-7 fill-current" /> : <Mic className="size-8" />}
              </button>
              <p className="h-5 text-sm tabular-nums text-muted-foreground">
                {recording ? `${elapsed.toFixed(1)}s · tap to stop` : blob ? 'Listen back, then submit' : 'Tap to record'}
              </p>
              {url && !recording && <audio controls src={url} className="h-9 w-full max-w-md opacity-80" />}
            </div>

            <StatusLine phase={phase} verdict={verdict} />
            {error && <ErrorNote className="mt-4">{error}</ErrorNote>}

            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              {phase === 'accepted' || phase === 'rejected' ? (
                <>
                  {phase === 'rejected' && (
                    <Button variant="outline" onClick={reset} className="gap-2">
                      <RotateCcw className="size-4" /> Try again
                    </Button>
                  )}
                  <Button onClick={next} className="gap-2">
                    Next sentence <ChevronRight className="size-4" />
                  </Button>
                </>
              ) : (
                <>
                  <Button onClick={submit} disabled={!blob || recording || phase !== 'idle'} className="gap-2">
                    {phase === 'uploading' || phase === 'judging' ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <UploadCloud className="size-4" />
                    )}
                    Submit recording
                  </Button>
                  {blob && (
                    <Button variant="ghost" onClick={reset} className="gap-2 text-muted-foreground">
                      <RotateCcw className="size-4" /> Re-record
                    </Button>
                  )}
                  <Button variant="ghost" onClick={skip} className="text-muted-foreground">
                    Skip
                  </Button>
                </>
              )}
            </div>
          </>
        ) : (
          <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-border/70">
            {loading ? <Loader2 className="size-5 animate-spin text-muted-foreground" /> : <p dir="rtl" className="font-nastaliq text-2xl text-muted-foreground/40">شکریہ</p>}
          </div>
        )}
      </Panel>

      <Panel eyebrow="This session" title={contributor.display_name ? `Thank you, ${contributor.display_name}` : 'Thank you'}>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border/80 bg-border/60">
          <Stat label="Accepted" value={session.accepted} />
          <Stat label="Rejected" value={session.rejected} warn />
        </dl>
        <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
          <Tip>Quiet room, phone or laptop microphone 20–30 cm away.</Tip>
          <Tip>Read exactly what is written. If the sentence has an error, skip it.</Tip>
          <Tip>Clips are checked automatically, then by another contributor before they count as validated.</Tip>
          <Tip>Up next: {queue.length - 1 > 0 ? `${queue.length - 1} more in this batch` : 'fetching more'}.</Tip>
        </ul>
      </Panel>
    </div>
  )
}

function StatusLine({ phase, verdict }) {
  if (phase === 'idle') return <div className="mt-4 h-6" />
  const map = {
    uploading: { icon: Loader2, text: 'Uploading…', cls: 'text-muted-foreground', spin: true },
    judging: { icon: Loader2, text: 'Checking the audio…', cls: 'text-muted-foreground', spin: true },
    accepted: { icon: Check, text: 'Accepted. It will be reviewed by another contributor.', cls: 'text-gold' },
    rejected: { icon: X, text: REJECT_LABELS[verdict] ?? `Rejected (${verdict}).`, cls: 'text-destructive' },
  }
  const m = map[phase]
  return (
    <p className={cn('mt-4 flex h-6 items-center justify-center gap-2 text-sm', m.cls)}>
      <m.icon className={cn('size-4', m.spin && 'animate-spin')} /> {m.text}
    </p>
  )
}

function Stat({ label, value, warn }) {
  return (
    <div className="bg-card/80 px-4 py-4">
      <dt className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</dt>
      <dd className={cn('mt-1 font-display text-3xl lining-nums tabular-nums', warn && value > 0 ? 'text-destructive' : 'text-foreground')}>
        {value}
      </dd>
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
