import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { byCode } from '@/lib/languages'
import StatCard from './StatCard'

/** What this site has collected so far, straight from the database. Refreshes on `tick`. */
export default function LiveStats({ lang, tick = 0 }) {
  const l = byCode(lang)
  const [stats, setStats] = useState(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    let alive = true
    api
      .stats(lang)
      .then((s) => alive && (setStats(s), setOffline(false)))
      .catch(() => alive && setOffline(true))
    return () => {
      alive = false
    }
  }, [lang, tick])

  return (
    <section className="mx-auto max-w-6xl px-6 pb-14">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-gold/80">Collected on awaaz</p>
          <h2 className="mt-1.5 font-display text-3xl font-medium tracking-tight">{l.name}, so far</h2>
        </div>
        {stats?.queue_depth > 0 && (
          <p className="text-xs text-muted-foreground">
            <span className="me-1.5 inline-block size-1.5 animate-pulse rounded-full bg-gold align-middle" />
            {stats.queue_depth} clip{stats.queue_depth === 1 ? '' : 's'} being processed
          </p>
        )}
      </div>
      {offline ? (
        <p className="rounded-xl border border-dashed border-border/70 px-5 py-6 text-sm text-muted-foreground">
          The database is not reachable. Start <code className="font-mono text-gold-soft/80">lowres-asr-api</code> and the worker to see live numbers.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border/80 bg-border/60 sm:grid-cols-5">
          <StatCard label="Sentences to read" value={stats ? stats.sentences.toLocaleString() : '—'} />
          <StatCard label="Contributors" value={stats ? stats.contributors.toLocaleString() : '—'} />
          <StatCard label="Clips recorded" value={stats ? stats.recordings_total.toLocaleString() : '—'} />
          <StatCard label="Awaiting review" value={stats ? stats.recordings_ready.toLocaleString() : '—'} />
          <StatCard label="Validated hours" value={stats ? stats.hours_validated.toFixed(2) : '—'} unit="h" />
        </div>
      )}
    </section>
  )
}
