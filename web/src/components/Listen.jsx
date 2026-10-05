import { useCallback, useEffect, useState } from 'react'
import { Check, Loader2, SkipForward, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { byCode } from '@/lib/languages'
import Panel from './Panel'
import ErrorNote from './ErrorNote'

/** Peer validation: play a clip, read the sentence, say whether they match. */
export default function Listen({ lang, contributor, onValidated }) {
  const l = byCode(lang)
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState({ good: 0, bad: 0 })

  const refill = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setQueue(await api.nextToValidate(lang, contributor.id, 5))
    } catch (e) {
      setQueue([])
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [lang, contributor.id])

  useEffect(() => {
    refill()
  }, [refill])

  const current = queue[0]

  async function vote(verdict) {
    if (!current) return
    setBusy(true)
    setError(null)
    try {
      await api.validate(current.recording_id, contributor.id, verdict)
      if (verdict !== 'skip') setDone((d) => ({ ...d, [verdict]: d[verdict] + 1 }))
      onValidated?.()
      setQueue((q) => {
        const rest = q.slice(1)
        if (rest.length === 0) refill()
        return rest
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <Panel
        eyebrow={`Listen · ${l.name}`}
        title={current ? 'Does the recording match the sentence?' : loading ? 'Loading…' : 'Nothing to review'}
        description={
          current
            ? 'Mark it good only if every word is spoken clearly and nothing is added or missing.'
            : loading
              ? ''
              : 'Every clip by other contributors has been reviewed by you already. Record some of your own instead.'
        }
      >
        {current ? (
          <>
            <div
              dir="rtl"
              className="font-nastaliq flex min-h-36 items-center justify-center rounded-xl border border-border/60 bg-background/40 px-8 py-6 text-center text-3xl text-ivory"
            >
              {current.sentence}
            </div>
            <div className="mt-5 flex justify-center">
              <audio key={current.recording_id} controls autoPlay src={current.audio_url} className="h-10 w-full max-w-md" />
            </div>
            {error && <ErrorNote className="mt-4">{error}</ErrorNote>}
            <div className="mt-6 flex items-center justify-center gap-3">
              <Button
                size="lg"
                variant="outline"
                disabled={busy}
                onClick={() => vote('bad')}
                className="gap-2 border-destructive/30 text-destructive hover:bg-destructive/10"
              >
                <X className="size-4" /> No
              </Button>
              <Button size="lg" disabled={busy} onClick={() => vote('good')} className="gap-2 px-8">
                {busy ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />} Yes
              </Button>
              <Button size="lg" variant="ghost" disabled={busy} onClick={() => vote('skip')} className="gap-2 text-muted-foreground">
                <SkipForward className="size-4" /> Skip
              </Button>
            </div>
          </>
        ) : (
          <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-border/70">
            {loading ? <Loader2 className="size-5 animate-spin text-muted-foreground" /> : <p dir="rtl" className="font-nastaliq text-2xl text-muted-foreground/40">سب ہو گیا</p>}
          </div>
        )}
      </Panel>

      <Panel eyebrow="This session" title="Your reviews">
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border/80 bg-border/60">
          <div className="bg-card/80 px-4 py-4">
            <dt className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Good</dt>
            <dd className="mt-1 font-display text-3xl lining-nums tabular-nums text-gold">{done.good}</dd>
          </div>
          <div className="bg-card/80 px-4 py-4">
            <dt className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Bad</dt>
            <dd className="mt-1 font-display text-3xl lining-nums tabular-nums text-foreground">{done.bad}</dd>
          </div>
        </dl>
        <p className="mt-6 text-sm leading-relaxed text-muted-foreground">
          A clip needs two independent "yes" votes to count as validated; two "no" votes remove it.
          You never see your own clips here, and you can only vote once on each.
        </p>
      </Panel>
    </div>
  )
}
