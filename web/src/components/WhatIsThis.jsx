import { FileText, Headphones, Mic } from 'lucide-react'
import { byCode } from '@/lib/languages'

/** Three plain sentences telling a first-time visitor what to do on the page. */
export default function WhatIsThis({ lang }) {
  const l = byCode(lang)
  const items = [
    {
      icon: Mic,
      tab: 'Speak',
      what: `Read short ${l.name} sentences aloud into your microphone. Each clip is saved with the text you read, which is exactly what a speech recognizer learns from. Agree once to share your voice freely; a name is optional.`,
    },
    {
      icon: Headphones,
      tab: 'Listen',
      what: `Hear other people's clips and say whether the recording matches the sentence. Two independent "yes" votes make a clip trustworthy enough to train on.`,
    },
    {
      icon: FileText,
      tab: 'Sentence studio',
      what: `Paste any ${l.name} text, such as a story or a news article. It is cut into clean, readable sentences and added to the pool that speakers read from. More sentences means more variety in the dataset.`,
    },
  ]

  return (
    <section className="mx-auto max-w-6xl px-6 pb-12">
      <div className="mb-6">
        <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-gold/80">What you can do here</p>
        <h2 className="mt-1.5 font-display text-3xl font-medium tracking-tight">Three tools, one goal</h2>
      </div>
      <ul className="grid gap-4 md:grid-cols-3">
        {items.map((it) => (
          <li key={it.tab} className="border-gilt rounded-xl p-5">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-full bg-gold/10 text-gold">
                <it.icon className="size-4" />
              </span>
              <h3 className="font-display text-xl font-medium">{it.tab}</h3>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{it.what}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
