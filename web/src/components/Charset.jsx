import { useState } from 'react'
import { Loader2, ScanSearch } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { byCode } from '@/lib/languages'
import { cn } from '@/lib/utils'
import Panel from './Panel'
import ErrorNote from './ErrorNote'

// Arabic-form code points that the normaliser folds into Urdu forms. Highlighting
// them tells you a source text was typed with an Arabic rather than Urdu keyboard.
const ARABIC_FORMS = new Set(['U+064A', 'U+0649', 'U+0643', 'U+0647', 'U+0629', 'U+0623', 'U+0625'])

export default function Charset({ lang }) {
  const l = byCode(lang)
  const [text, setText] = useState('')
  const [rows, setRows] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      setRows(await api.charset(lang, text))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const total = rows?.reduce((s, r) => s + r.count, 0) ?? 0
  const max = rows?.[0]?.count ?? 1
  const stray = rows?.filter((r) => ARABIC_FORMS.has(r.codepoint)).length ?? 0

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <Panel
        eyebrow="Inventory"
        title="Which letters does this text use?"
        description={`Every code point, counted. Use it on the Common Voice ${l.code} sentence corpus to find the ${l.name}-specific letters that belong in preserve_chars, and to catch stray Arabic-form letters.`}
      >
        <Textarea
          dir="rtl"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="متن…"
          className="font-nastaliq min-h-72 resize-y bg-background/50 text-[17px] leading-[2.2] focus-visible:ring-gold/40"
        />
        <div className="mt-4 flex items-center gap-2">
          <Button onClick={run} disabled={busy || !text.trim()} className="gap-2">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <ScanSearch className="size-4" />}
            Count characters
          </Button>
          {rows && (
            <p className="ms-auto text-xs text-muted-foreground">
              {rows.length} distinct · {total.toLocaleString()} total
              {stray > 0 && <span className="text-destructive"> · {stray} Arabic-form</span>}
            </p>
          )}
        </div>
        {error && <ErrorNote className="mt-4">{error}</ErrorNote>}
      </Panel>

      <Panel eyebrow="Code points" title={rows ? 'Most frequent first' : 'No text analysed'}>
        {rows ? (
          <ScrollArea className="h-[30rem]">
            <Table>
              <TableHeader>
                <TableRow className="border-border/60 hover:bg-transparent">
                  <TableHead className="w-14 text-muted-foreground">Glyph</TableHead>
                  <TableHead className="w-24 text-muted-foreground">Code</TableHead>
                  <TableHead className="text-muted-foreground">Name</TableHead>
                  <TableHead className="w-40 text-end text-muted-foreground">Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => {
                  const arabicForm = ARABIC_FORMS.has(r.codepoint)
                  return (
                    <TableRow key={r.codepoint} className={cn('border-border/40', arabicForm && 'bg-destructive/[0.04]')}>
                      <TableCell className="font-nastaliq text-xl text-ivory">{r.char}</TableCell>
                      <TableCell className={cn('font-mono text-xs', arabicForm ? 'text-destructive' : 'text-gold/80')}>
                        {r.codepoint}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {r.name.replace('ARABIC LETTER ', '').toLowerCase()}
                      </TableCell>
                      <TableCell className="text-end">
                        <div className="flex items-center justify-end gap-3">
                          <span className="h-1 w-20 overflow-hidden rounded-full bg-muted">
                            <span
                              className={cn('block h-full rounded-full', arabicForm ? 'bg-destructive/60' : 'bg-gold/70')}
                              style={{ width: `${(r.count / max) * 100}%` }}
                            />
                          </span>
                          <span className="w-10 font-display text-base tabular-nums">{r.count}</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </ScrollArea>
        ) : (
          <div className="flex h-[30rem] items-center justify-center rounded-lg border border-dashed border-border/70">
            <p className="font-display text-5xl text-muted-foreground/25">U+06CC</p>
          </div>
        )}
      </Panel>
    </div>
  )
}
