import { useState } from 'react'
import { Loader2, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import Panel from './Panel'
import ErrorNote from './ErrorNote'

const AGE_BANDS = ['under 18', '18–29', '30–39', '40–49', '50–59', '60+']
const GENDERS = ['female', 'male', 'other', 'prefer not to say']

/**
 * The one screen every contributor sees once. Name is optional; the two consents are
 * not. Nothing here is verified and nothing identifies the person unless they choose
 * to type their name.
 */
export default function ConsentGate({ onConsent, langName }) {
  const [name, setName] = useState('')
  const [cc0, setCc0] = useState(false)
  const [storage, setStorage] = useState(false)
  const [age, setAge] = useState('')
  const [gender, setGender] = useState('')
  const [region, setRegion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onConsent({
        display_name: name || null,
        consent_cc0: cc0,
        consent_storage: storage,
        age_band: age || null,
        gender: gender || null,
        region: region || null,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel
      eyebrow="Before you start"
      title="Your voice, given freely"
      description={`Recordings of ${langName} speech are only useful if they can be shared openly with everyone who wants to build tools for the language. Please read and agree to the two points below.`}
      className="mx-auto max-w-2xl"
    >
      <form onSubmit={submit} className="space-y-7">
        <fieldset className="space-y-4">
          <ConsentRow
            id="cc0"
            checked={cc0}
            onChange={setCc0}
            title="I release my recordings and sentences into the public domain (CC0)."
            body="Anyone, including companies and researchers, may use them for any purpose without asking me or crediting me. This is what lets the data be combined with Mozilla Common Voice and used to train models."
          />
          <ConsentRow
            id="storage"
            checked={storage}
            onChange={setStorage}
            title="I agree that my recordings are stored and published."
            body="A voice can identify a person even without a name. The audio will be kept on this project's servers and may be published in open datasets. I can ask for my clips to be withdrawn from this site, but copies already downloaded by others cannot be recalled."
          />
        </fieldset>

        <div className="space-y-2">
          <Label htmlFor="name" className="text-muted-foreground">
            Name <span className="text-muted-foreground/60">(optional, shown as the contributor on your clips)</span>
          </Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={80}
            placeholder="Leave blank to stay anonymous"
            className="bg-background/50"
          />
        </div>

        <details className="group rounded-lg border border-border/60 bg-background/30 px-4 py-3">
          <summary className="cursor-pointer text-sm text-muted-foreground group-open:text-foreground">
            About you <span className="text-muted-foreground/60">(optional, helps build a balanced dataset)</span>
          </summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Age</Label>
              <Select value={age} onValueChange={setAge}>
                <SelectTrigger className="bg-background/50"><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{AGE_BANDS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Gender</Label>
              <Select value={gender} onValueChange={setGender}>
                <SelectTrigger className="bg-background/50"><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{GENDERS.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="region" className="text-xs text-muted-foreground">Home district</Label>
              <Input id="region" value={region} onChange={(e) => setRegion(e.target.value)} maxLength={80} placeholder="e.g. Poonch" className="bg-background/50" />
            </div>
          </div>
        </details>

        {error && <ErrorNote>{error}</ErrorNote>}

        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            We store a random ID in this browser so your clips stay grouped together. No cookies, no tracking.
          </p>
          <Button type="submit" disabled={!cc0 || !storage || busy} className="gap-2">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
            Agree and continue
          </Button>
        </div>
      </form>
    </Panel>
  )
}

function ConsentRow({ id, checked, onChange, title, body }) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer gap-3 rounded-lg border border-border/60 bg-background/40 p-4 transition-colors has-[[data-state=checked]]:border-gold/40 has-[[data-state=checked]]:bg-gold/[0.04]"
    >
      <Checkbox id={id} checked={checked} onCheckedChange={(v) => onChange(v === true)} className="mt-0.5" />
      <span>
        <span className="block text-sm font-medium text-foreground">{title}</span>
        <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{body}</span>
      </span>
    </label>
  )
}
