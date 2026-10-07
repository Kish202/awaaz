import { byCode } from '@/lib/languages'
import StatCard from './StatCard'

export default function Hero({ lang }) {
  const l = byCode(lang)
  const cv = l.commonVoice
  return (
    <section className="relative mx-auto max-w-6xl px-6 pt-20 pb-14">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 mx-auto h-px w-2/3 bg-gradient-to-r from-transparent via-gold/40 to-transparent" />

      <p className="rise text-[11px] font-medium uppercase tracking-[0.3em] text-gold/80">
        {l.iso} · {l.region}
      </p>

      <h1 className="rise mt-5 font-display text-5xl leading-[1.05] font-medium tracking-tight text-balance sm:text-6xl lg:text-7xl [animation-delay:60ms]">
        Teaching computers to hear{' '}
        <span className="text-gold-gradient italic">{l.name}</span>.
      </h1>

      <div className="rise mt-6 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between [animation-delay:120ms]">
        <div className="max-w-xl space-y-3 text-base leading-relaxed text-muted-foreground">
          <p>
            {l.name} has no speech-to-text. Siri, Google and WhatsApp voice notes cannot
            understand it, because no one has collected enough recorded speech with matching
            text to train a model.
          </p>
          <p>
            <span className="text-foreground">awaaz</span> collects that speech, one answer at a
            time. It asks you simple questions in English or Hindi and you reply in {l.name},
            typed or spoken. Other speakers check the clips. Everything collected is released
            freely so anyone can build a {l.name} speech recognizer; a first one is being
            trained here.
          </p>
        </div>
        <p
          dir="rtl"
          className="font-nastaliq text-3xl text-ivory/90 lg:text-right"
          aria-label={`Sample ${l.name} sentence`}
        >
          {l.sample}
        </p>
      </div>

      <div className="rise mt-12 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border/80 bg-border/60 sm:grid-cols-4 [animation-delay:180ms]">
        <StatCard label="Validated hours" value={cv.validated.toFixed(1)} unit="h" />
        <StatCard label="Speakers" value={cv.speakers} warn={cv.speakers < 20} />
        <StatCard label="Unique sentences" value={cv.sentences.toLocaleString()} />
        <StatCard label="Recorded clips" value={cv.clips.toLocaleString()} />
      </div>
      <p className="mt-3 text-xs text-muted-foreground/80">
        Mozilla Common Voice 26.0 · {l.note}
      </p>
    </section>
  )
}
