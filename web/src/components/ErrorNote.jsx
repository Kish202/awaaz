import { AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function ErrorNote({ children, className }) {
  return (
    <p
      role="alert"
      className={cn(
        'flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/[0.06] px-3 py-2.5 text-sm text-destructive',
        className,
      )}
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  )
}
