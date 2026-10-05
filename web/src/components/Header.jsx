import { Code2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import LanguageSwitch from './LanguageSwitch'

export default function Header({ lang, onLang }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <a href="#" className="group flex items-baseline gap-3">
          <span className="font-display text-2xl font-medium lowercase tracking-tight text-foreground">
            awaaz
          </span>
          <span className="font-nastaliq text-base text-gold/90 leading-none">آواز</span>
          <span className="hidden text-[11px] lowercase tracking-[0.18em] text-muted-foreground sm:inline">
            speech data for gojri &amp; pahari
          </span>
        </a>
        <div className="flex items-center gap-3">
          <LanguageSwitch value={lang} onChange={onLang} />
          <Button variant="ghost" size="icon" asChild className="text-muted-foreground hover:text-foreground">
            <a href="https://github.com" target="_blank" rel="noreferrer" aria-label="Source">
              <Code2 className="size-4" />
            </a>
          </Button>
        </div>
      </div>
    </header>
  )
}
