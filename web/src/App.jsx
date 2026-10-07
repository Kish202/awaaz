import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { useContributor } from '@/lib/contributor'
import { byCode } from '@/lib/languages'
import Header from '@/components/Header'
import Hero from '@/components/Hero'
import WhatIsThis from '@/components/WhatIsThis'
import LiveStats from '@/components/LiveStats'
import ConsentGate from '@/components/ConsentGate'
import Talk from '@/components/Talk'
import Contribute from '@/components/Contribute'
import Listen from '@/components/Listen'
import SentenceStudio from '@/components/SentenceStudio'
import Transcribe from '@/components/Transcribe'
import Charset from '@/components/Charset'
import Pipeline from '@/components/Pipeline'

const TABS = [
  ['talk', 'Talk'],
  ['contribute', 'Speak'],
  ['listen', 'Listen'],
  ['sentences', 'Add text'],
  ['transcribe', 'Transcribe'],
  ['charset', 'Characters'],
]

export default function App() {
  const [lang, setLang] = useState('phr')
  const [tick, setTick] = useState(0)
  const { contributor, profile, consent, forget, refresh } = useContributor()
  const bump = () => {
    setTick((t) => t + 1)
    refresh()
  }
  const l = byCode(lang)

  // Talk, Speak and Listen need a consenting contributor; everything else does not.
  const gated = (node) =>
    contributor ? node : <ConsentGate langName={l.name} onConsent={consent} />

  return (
    <div className="grain min-h-dvh">
      <Header lang={lang} onLang={setLang} />
      <main>
        <Hero key={lang} lang={lang} />
        <WhatIsThis lang={lang} />
        <LiveStats lang={lang} tick={tick} />

        <section id="workbench" className="mx-auto max-w-6xl px-6 pb-24">
          <Tabs defaultValue="talk">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
              <TabsList className="h-11 rounded-full border border-border/80 bg-card/60 p-1">
                {TABS.map(([v, label]) => (
                  <TabsTrigger
                    key={v}
                    value={v}
                    className="rounded-full px-4 text-sm text-muted-foreground data-[state=active]:bg-accent data-[state=active]:text-gold-soft data-[state=active]:shadow-none"
                  >
                    {label}
                  </TabsTrigger>
                ))}
              </TabsList>
              {contributor ? (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="inline-block size-1.5 rounded-full bg-gold" />
                  {contributor.display_name ? contributor.display_name : 'Anonymous contributor'}
                  {profile && (
                    <span className="text-muted-foreground/70">
                      · {profile.response_count} answers · {profile.recording_count} clips · {profile.validation_count} reviews
                    </span>
                  )}
                  <Button variant="link" size="sm" onClick={forget} className="h-auto p-0 text-xs text-muted-foreground/70">
                    forget me on this device
                  </Button>
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">Not yet contributing · consent is asked once</p>
              )}
            </div>

            <TabsContent value="talk" className="rise">
              {gated(<Talk key={lang} lang={lang} contributor={contributor} onAnswered={bump} />)}
            </TabsContent>
            <TabsContent value="contribute" className="rise">
              {gated(<Contribute key={lang} lang={lang} contributor={contributor} onRecorded={bump} />)}
            </TabsContent>
            <TabsContent value="listen" className="rise">
              {gated(<Listen key={lang} lang={lang} contributor={contributor} onValidated={bump} />)}
            </TabsContent>
            <TabsContent value="sentences" className="rise">
              <SentenceStudio lang={lang} contributor={contributor} onContributed={bump} />
            </TabsContent>
            <TabsContent value="transcribe" className="rise">
              <Transcribe lang={lang} />
            </TabsContent>
            <TabsContent value="charset" className="rise">
              <Charset lang={lang} />
            </TabsContent>
          </Tabs>
        </section>

        <Pipeline />
      </main>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-3 px-6 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <p>
            <span className="font-display text-base lowercase text-foreground">awaaz</span> · open tooling for
            Gojri and Pahari-Pothwari
          </p>
          <p>Contributions are CC0 · Data: Mozilla Common Voice 26.0 · Models: Whisper · Code: MIT</p>
        </div>
      </footer>
    </div>
  )
}
