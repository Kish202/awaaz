import { cn } from '@/lib/utils'

/** A gilt-edged card with an eyebrow label, a serif title and an optional action slot. */
export default function Panel({ eyebrow, title, description, action, children, className }) {
  return (
    <section className={cn('border-gilt rounded-xl p-6 shadow-[0_30px_60px_-30px_oklch(0_0_0/70%)]', className)}>
      <header className="mb-5 flex items-start justify-between gap-4">
        <div>
          {eyebrow && (
            <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-gold/80">{eyebrow}</p>
          )}
          <h2 className="mt-1.5 font-display text-2xl font-medium tracking-tight text-foreground">{title}</h2>
          {description && <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-muted-foreground">{description}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  )
}
