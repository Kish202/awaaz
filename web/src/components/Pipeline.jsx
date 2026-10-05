import { BookOpenText, Mic2, Scissors, Waves } from 'lucide-react'

const STEPS = [
  {
    icon: BookOpenText,
    title: 'Find text',
    body: 'Books, folk tales, school readers, typed-up transcripts. The author must agree to release the sentences freely.',
    code: 'you',
  },
  {
    icon: Scissors,
    title: 'Make sentences',
    body: 'The Sentence studio cuts the text into short, readable sentences and removes anything a volunteer could not read aloud.',
    code: 'this site',
  },
  {
    icon: Mic2,
    title: 'Record voices',
    body: 'The sentences go to Mozilla Common Voice, where native speakers record them and check each other’s recordings.',
    code: 'volunteers',
  },
  {
    icon: Waves,
    title: 'Train and test',
    body: 'Those recordings teach a speech recognizer. Come back to the Transcribe tab and see if it understands you.',
    code: 'this site',
  },
]

export default function Pipeline() {
  return (
    <section className="mx-auto max-w-6xl px-6 pb-20">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-gold/80">How it fits together</p>
          <h2 className="mt-1.5 font-display text-3xl font-medium tracking-tight">From a book to a voice assistant</h2>
        </div>
        <p className="hidden max-w-sm text-sm text-muted-foreground sm:block">
          Every time this loop runs there are more sentences, more hours of speech, and a better model.
        </p>
      </div>
      <ol className="grid gap-px overflow-hidden rounded-xl border border-border/80 bg-border/60 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s.title} className="group relative bg-card/80 p-6 transition-colors hover:bg-card">
            <span className="absolute right-6 top-6 font-display text-4xl text-gold/15 transition-colors group-hover:text-gold/30">
              {String(i + 1).padStart(2, '0')}
            </span>
            <s.icon className="size-5 text-gold/80" />
            <h3 className="mt-5 font-display text-xl font-medium">{s.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
            <code className="mt-4 inline-block rounded-md border border-border/60 bg-background/60 px-2 py-1 font-mono text-[11px] text-gold-soft/80">
              {s.code}
            </code>
          </li>
        ))}
      </ol>
    </section>
  )
}
