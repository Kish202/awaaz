import { FileText, Headphones, MessageCircleQuestion, Mic } from 'lucide-react'
import { byCode } from '@/lib/languages'

/** Plain sentences telling a first-time visitor what to do on the page. */
export default function WhatIsThis({ lang }) {
  const l = byCode(lang)
  const items = [
    {
      icon: MessageCircleQuestion,
      tab: 'Talk',
      what: `The easiest way to help. awaaz asks you a question in English or Hindi ("What did you eat today?", "How do you say 'it is raining'?") and you answer in ${l.name}, by typing, by speaking, or both. Over a thousand questions about food, family, weather, work and village life.`,
    },
    {
      icon: Mic,
      tab: 'Speak',
      what: `Read short ${l.name} sentences aloud into your microphone. Each clip is saved with the text you read, which is exactly what a speech recognizer learns from. Agree once to share your voice freely; a name is optional.`,
    },
    {
      icon: Headphones,
      tab: 'Listen',
      what: `Hear other people's clips and say whether the recording matches the text. Two independent "yes" votes make a clip trustworthy enough to train on.`,
    },
    {
      icon: FileText,
      tab: 'Add text',
      what: `Already have ${l.name} text, like a story or a news article? Paste it. It is cut into clean, readable sentences and added to the pool that speakers read from.`,
    },
  ]

  return (
    <section className="mx-auto max-w-6xl px-6 pb-12">
      <div className="mb-6">
        <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-gold/80">What you can do here</p>
        <h2 className="mt-1.5 font-display text-3xl font-medium tracking-tight">Four ways to help, one goal</h2>
      </div>
      <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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
