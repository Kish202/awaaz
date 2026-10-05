import { cn } from '@/lib/utils'

export default function StatCard({ label, value, unit, warn = false, className }) {
  return (
    <div className={cn('group relative bg-card/80 px-5 py-5 transition-colors hover:bg-card', className)}>
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 flex items-baseline gap-1 font-display text-4xl font-medium lining-nums tabular-nums text-foreground">
        {value}
        {unit && <span className="text-lg text-muted-foreground">{unit}</span>}
      </p>
      <span
        aria-hidden
        className={cn(
          'absolute right-5 top-5 size-1.5 rounded-full transition-transform group-hover:scale-125',
          warn ? 'bg-destructive/80 shadow-[0_0_12px_oklch(0.62_0.17_25/60%)]' : 'bg-gold/70 shadow-[0_0_12px_oklch(0.8_0.1_85/50%)]',
        )}
      />
    </div>
  )
}
