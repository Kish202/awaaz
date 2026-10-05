import { useEffect, useMemo, useRef, useState } from 'react'
import { AudioLines, Loader2, Mic, Square, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { byCode } from '@/lib/languages'
import { cn } from '@/lib/utils'
import Panel from './Panel'
import ErrorNote from './ErrorNote'

export default function Transcribe({ lang }) {
  const l = byCode(lang)
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [recording, setRecording] = useState(false)
  const [model, setModel] = useState('openai/whisper-small')
  const recorder = useRef(null)
  const chunks = useRef([])
  const inputRef = useRef(null)
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  useEffect(() => () => url && URL.revokeObjectURL(url), [url])

  async function toggleRecord() {
    if (recording) {
      recorder.current?.stop()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunks.current = []
      rec.ondataavailable = (e) => chunks.current.push(e.data)
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' })
        setFile(new File([blob], `recording.${blob.type.includes('mp4') ? 'm4a' : 'webm'}`, { type: blob.type }))
        setResult(null)
        setRecording(false)
      }
      rec.start()
      recorder.current = rec
      setRecording(true)
    } catch {
      setError('Microphone access was denied.')
    }
  }

  async function run() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.transcribe(lang, file, model))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <Panel
        eyebrow="Audio"
        title="Record or upload"
        description={`Audition a checkpoint on ${l.name} speech. Whisper is seeded from Urdu, the nearest supported language, and fine-tuned on Common Voice ${l.code}.`}
      >
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const f = e.dataTransfer.files?.[0]
            if (f) {
              setFile(f)
              setResult(null)
            }
          }}
          className={cn(
            'relative flex min-h-56 flex-col items-center justify-center rounded-lg border border-dashed transition-colors',
            file ? 'border-gold/40 bg-gold/[0.04]' : 'border-border/80 bg-background/40 hover:border-gold/30',
          )}
        >
          <button
            onClick={toggleRecord}
            aria-pressed={recording}
            aria-label={recording ? 'Stop recording' : 'Start recording'}
            className={cn(
              'relative grid size-20 place-items-center rounded-full border transition-all',
              recording
                ? 'border-destructive/50 bg-destructive/15 text-destructive'
                : 'border-gold/40 bg-gradient-to-b from-card to-background text-gold hover:scale-[1.03] hover:border-gold/70',
            )}
          >
            {recording && <span className="absolute inset-0 animate-ping rounded-full border border-destructive/40" />}
            {recording ? <Square className="size-6 fill-current" /> : <Mic className="size-7" />}
          </button>
          <p className="mt-4 text-sm text-muted-foreground">
            {recording ? 'Listening… tap to stop' : file ? file.name : 'Tap to record, or drop an audio file'}
          </p>
          {url && !recording && <audio controls src={url} className="mt-4 h-9 w-4/5 opacity-80" />}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={run} disabled={!file || busy} className="gap-2">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <AudioLines className="size-4" />}
            Transcribe
          </Button>
          <Button variant="outline" className="gap-2" onClick={() => inputRef.current?.click()}>
            <Upload className="size-4" /> Upload
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept="audio/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) {
                setFile(f)
                setResult(null)
              }
              e.target.value = ''
            }}
          />
          <label className="ms-auto flex items-center gap-2 text-xs text-muted-foreground">
            Model
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              spellCheck={false}
              className="w-56 rounded-md border border-input bg-background/60 px-2 py-1 font-mono text-[11px] text-foreground outline-none focus:border-gold/50"
            />
          </label>
        </div>
        {error && <ErrorNote className="mt-4">{error}</ErrorNote>}
      </Panel>

      <Panel
        eyebrow="Transcript"
        title={result ? 'Heard' : 'Awaiting audio'}
        description={result ? `Decoded with ${result.model}` : 'The raw decode and its normalised form appear here.'}
      >
        {result ? (
          <div className="space-y-6">
            <blockquote dir="rtl" className="font-nastaliq border-s-2 border-gold/50 ps-5 text-3xl leading-[2.1] text-ivory">
              {result.text || <span className="text-muted-foreground/60">—</span>}
            </blockquote>
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="outline" className="border-border/80 text-muted-foreground">normalised</Badge>
                <span className="text-[11px] text-muted-foreground">same rules as WER scoring</span>
              </div>
              <p dir="rtl" className="font-nastaliq rounded-lg border border-border/60 bg-background/40 px-4 py-3 text-lg text-foreground/90">
                {result.normalized || '—'}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-border/70">
            <Waveform />
          </div>
        )}
      </Panel>
    </div>
  )
}

function Waveform() {
  const bars = Array.from({ length: 28 }, (_, i) => 0.25 + 0.75 * Math.abs(Math.sin(i * 0.7)))
  return (
    <div className="flex h-16 items-center gap-1" aria-hidden>
      {bars.map((h, i) => (
        <span
          key={i}
          className="w-[3px] rounded-full bg-gradient-to-t from-gold/10 to-gold/50"
          style={{ height: `${h * 100}%` }}
        />
      ))}
    </div>
  )
}
