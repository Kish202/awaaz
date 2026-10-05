import { cn } from '@/lib/utils'
import { LANGUAGES } from '@/lib/languages'

export default function LanguageSwitch({ value, onChange }) {
  return (
    <div
      role="radiogroup"
      aria-label="Language"
      className="relative flex items-center rounded-full border border-border/80 bg-card/60 p-1 text-sm shadow-[inset_0_1px_0_0_oklch(1_0_0/4%)]"
    >
      {LANGUAGES.map((l) => {
        const active = l.code === value
        return (
          <button
            key={l.code}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(l.code)}
            className={cn(
              'relative z-10 flex items-center gap-2 rounded-full px-3.5 py-1.5 transition-colors duration-300',
              active ? 'text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {active && (
              <span
                aria-hidden
                className="absolute inset-0 -z-10 rounded-full bg-gradient-to-b from-gold-soft to-gold shadow-[0_1px_0_0_oklch(1_0_0/35%)_inset,0_6px_18px_-6px_oklch(0.8_0.1_85/60%)]"
              />
            )}
            <span className="font-medium tracking-tight">{l.name}</span>
            <span className={cn('font-nastaliq text-[13px] leading-none', active ? 'opacity-90' : 'opacity-60')}>
              {l.native}
            </span>
          </button>
        )
      })}
    </div>
  )
}
