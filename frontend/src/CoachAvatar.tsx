import { useState, useEffect, useCallback, useRef } from 'react'
import {
  AlertCircle, BadgeEuro, Heart, Loader2, MessageSquareWarning, MessagesSquare, PhoneOff, Play, RotateCcw, Video,
} from 'lucide-react'
import ScoreCard from '@/components/ScoreCard'
import { DEMO_ANALYSIS } from './demo'
import { initials, personaFor, type Persona } from './personas'

interface PracticeSide {
  id: string
  label: string
  user_role: string
  avatar_role: string
  user_goal: string
}

interface Scenario {
  id: string
  title: string
  category: string
  icon: string
  description: string
  avatar_role: string
  user_goal: string
  practice_sides: PracticeSide[]
  rubric?: { key: string; label: string }[]
  side_prompt?: string
}

interface SessionState {
  status: 'idle' | 'selecting' | 'creating' | 'active' | 'analyzing' | 'done' | 'error'
  embedUrl?: string
  sessionId?: string
  conversationId?: string
  sessionToken?: string
  scenario?: Scenario
  practiceSide?: PracticeSide
  error?: string
}

export interface Analysis {
  empathy_score: number
  empathy_feedback: string
  clarity_score: number
  clarity_feedback: string
  result_score: number
  result_feedback: string
  summary: string
  transcript?: string
  better_phrasings?: { original: string; better: string; why: string }[]
  counterpart_journey?: string
  asr_notes?: string[]
  error?: string
  note?: string
}

const DEFAULT_GAUGE_LABELS = ['Empathie', 'Klarheit', 'Ergebnis']

const SCENARIO_ICONS: Record<string, typeof Heart> = {
  dollar: BadgeEuro,
  'message-circle': MessageSquareWarning,
  heart: Heart,
}

function rubricLabels(scenario?: Scenario): string[] {
  const labels = scenario?.rubric?.map(r => r.label) ?? []
  return labels.length === 3 ? labels : DEFAULT_GAUGE_LABELS
}

function Portrait({ persona, size = 'lg', ringing = false }: { persona: Persona; size?: 'sm' | 'lg'; ringing?: boolean }) {
  return (
    <div className={`portrait portrait--${size} ${ringing ? 'portrait--ringing' : ''}`} aria-hidden="true">
      <span>{initials(persona.name)}</span>
    </div>
  )
}

function useElapsed(running: boolean): string {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!running) return
    setSeconds(0)
    const timer = window.setInterval(() => setSeconds(s => s + 1), 1000)
    return () => window.clearInterval(timer)
  }, [running])
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export default function CoachAvatar() {
  const [session, setSession] = useState<SessionState>({ status: 'selecting' })
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = useState('salary')
  const [selectedSideId, setSelectedSideId] = useState('')
  const [setupStatus, setSetupStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)

  useEffect(() => {
    const demo = new URLSearchParams(window.location.search).get('demo')

    fetch('/api/scenarios')
      .then(r => r.json())
      .then(data => {
        const list: Scenario[] = data.scenarios || []
        setScenarios(list)
        // ?demo=auswertung shows a sample analysis for screenshots, without starting a Tavus call
        if (demo === 'auswertung' && list[0]) {
          setSession({ status: 'done', scenario: list[0], practiceSide: list[0].practice_sides[0] })
          setAnalysis(DEMO_ANALYSIS)
        }
      })
      .catch(() => setScenarios([]))

    fetch('/api/session/status')
      .then(r => r.json())
      .then(data => {
        if (!data.configured) throw new Error('Tavus ist nicht konfiguriert.')
        setSetupStatus('ready')
      })
      .catch(() => setSetupStatus('error'))
  }, [])

  const startCoaching = useCallback(async (scenario: Scenario, practiceSide: PracticeSide) => {
    setSession({ status: 'creating', scenario, practiceSide })
    setAnalysis(null)
    try {
      const resp = await fetch('/api/session/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenario.id, practice_side: practiceSide.id, sandbox: false })
      })
      const data = await resp.json()

      if (!resp.ok || data.error) {
        setSession({ status: 'error', error: data.error || data.detail || 'Session konnte nicht erstellt werden.', scenario, practiceSide })
        return
      }

      setSession({
        status: 'active',
        embedUrl: data.embed_url,
        sessionId: data.session_id,
        conversationId: data.conversation_id,
        sessionToken: data.session_token,
        scenario,
        practiceSide
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Fehler bei Session-Erstellung'
      setSession({ status: 'error', error: message, scenario, practiceSide })
    }
  }, [])

  const stopAndAnalyze = useCallback(async () => {
    const conversationId = session.conversationId || session.sessionId
    if (!conversationId) return
    setSession(s => ({ ...s, status: 'analyzing' }))

    try {
      const resp = await fetch('/api/session/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-Token': session.sessionToken || '' },
        body: JSON.stringify({
          conversation_id: conversationId,
          scenario_id: session.scenario?.id || 'salary',
          practice_side: session.practiceSide?.id
        })
      })
      const result = await resp.json()
      setAnalysis(resp.ok ? result : ({ error: result.error || result.detail || 'Analyse fehlgeschlagen' } as Analysis))
      setSession(s => ({ ...s, status: 'done' }))
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Analyse fehlgeschlagen'
      setAnalysis({ error: message } as Analysis)
      setSession(s => ({ ...s, status: 'done' }))
    }
  }, [session.conversationId, session.sessionId, session.sessionToken, session.scenario?.id, session.practiceSide?.id])

  // The PAL can hang up itself (Tavus end_call). Poll the status and start the analysis automatically.
  const autoAnalyzeStarted = useRef(false)
  useEffect(() => {
    if (session.status !== 'active' || !session.conversationId) return
    autoAnalyzeStarted.current = false
    const conversationId = session.conversationId
    const timer = window.setInterval(async () => {
      try {
        const resp = await fetch(`/api/session/${conversationId}/status`, {
          headers: { 'X-Session-Token': session.sessionToken || '' }
        })
        if (!resp.ok) return
        const data = await resp.json()
        if (data.status === 'ended' && !autoAnalyzeStarted.current) {
          autoAnalyzeStarted.current = true
          window.clearInterval(timer)
          stopAndAnalyze()
        }
      } catch {
        // network hiccup: try again on the next tick
      }
    }, 5000)
    return () => window.clearInterval(timer)
  }, [session.status, session.conversationId, session.sessionToken, stopAndAnalyze])

  const inCall = session.status === 'active' || session.status === 'analyzing'
  const elapsed = useElapsed(session.status === 'active')

  const reset = useCallback(() => {
    setSession({ status: 'selecting' })
    setAnalysis(null)
    window.scrollTo({ top: 0 })
  }, [])

  if (setupStatus === 'loading') {
    return (
      <section className="state-card glass">
        <Loader2 className="spin" size={28} />
        <h2>Training wird vorbereitet</h2>
        <p>Die Szenarien und der Video-Avatar werden geladen.</p>
      </section>
    )
  }

  if (setupStatus === 'error') {
    return (
      <section className="state-card glass">
        <AlertCircle size={28} />
        <h2>Der Video-Avatar ist gerade nicht erreichbar</h2>
        <p>Lade die Seite in ein paar Minuten neu. Die Audio-Analyse funktioniert unabhängig davon.</p>
        <button className="btn btn-secondary" onClick={() => window.location.reload()}>
          <RotateCcw size={18} /> Neu laden
        </button>
      </section>
    )
  }

  // ---- SCENARIO SELECTION ----
  if (session.status === 'selecting') {
    const selectedScenario = scenarios.find(s => s.id === selectedScenarioId) || scenarios[0]
    const selectedSide = selectedScenario?.practice_sides.find(side => side.id === selectedSideId) || selectedScenario?.practice_sides[0]
    const persona = selectedSide ? personaFor(selectedSide.id, selectedSide.avatar_role) : null

    return (
      <>
        <header className="page-intro">
          <h1>Übe das Gespräch, bevor es zählt.</h1>
          <p>
            Wähle eine Situation und dein Gegenüber. Der Avatar spielt die Rolle live per Video,
            danach bekommst du eine Auswertung mit besseren Formulierungen.
          </p>
        </header>

        <div className="setup">
          <div className="setup-steps">
            <section className="step" aria-labelledby="step-situation">
              <h2 id="step-situation"><span className="step-no">1</span>Welche Situation willst du üben?</h2>
              <div className="scenario-grid">
                {scenarios.map(s => {
                  const Icon = SCENARIO_ICONS[s.icon] || MessagesSquare
                  const active = selectedScenario?.id === s.id
                  return (
                    <button
                      key={s.id}
                      className={`scenario-card glass ${active ? 'is-active' : ''}`}
                      aria-pressed={active}
                      onClick={() => {
                        setSelectedScenarioId(s.id)
                        setSelectedSideId(s.practice_sides[0]?.id || '')
                      }}
                    >
                      <span className="icon-box"><Icon size={22} strokeWidth={1.6} /></span>
                      <span className="scenario-category">{s.category}</span>
                      <strong>{s.title}</strong>
                      <span className="scenario-desc">{s.description}</span>
                    </button>
                  )
                })}
              </div>
            </section>

            {selectedScenario && (
              <section className="step" aria-labelledby="step-counterpart">
                <h2 id="step-counterpart">
                  <span className="step-no">2</span>
                  {selectedScenario.id === 'dating' ? 'Mit wem hast du dein Date?' : 'Welche Seite übernimmst du?'}
                </h2>
                <div className="persona-grid">
                  {selectedScenario.practice_sides.map(side => {
                    const p = personaFor(side.id, side.avatar_role)
                    const active = selectedSide?.id === side.id
                    return (
                      <button
                        key={side.id}
                        className={`persona-card glass ${active ? 'is-active' : ''}`}
                        aria-pressed={active}
                        onClick={() => setSelectedSideId(side.id)}
                      >
                        <Portrait persona={p} size="sm" />
                        <span className="persona-text">
                          <span className="persona-side">{side.label}</span>
                          <strong>Gegenüber: {p.name}</strong>
                          <span>{p.role}</span>
                        </span>
                      </button>
                    )
                  })}
                </div>
              </section>
            )}
          </div>

          {selectedScenario && selectedSide && persona && (
            <aside className="stage stage--preview" aria-label="Vorschau des Gesprächs">
              <div className="stage-top">
                <span className="stage-chip"><Video size={14} /> Video-Call</span>
                <span className="stage-chip stage-chip--ready"><span className="dot" /> Bereit</span>
              </div>
              <div className="stage-person">
                <Portrait persona={persona} />
                <h3>{persona.name}</h3>
                <p className="stage-role">{persona.role}</p>
                {persona.mood && <p className="stage-mood">{persona.mood}</p>}
              </div>
              <div className="stage-brief">
                <h4>Dein Ziel</h4>
                <p>{selectedSide.user_goal}</p>
                <h4>Bewertet wird</h4>
                <ul className="criteria">
                  {rubricLabels(selectedScenario).map(l => <li key={l}>{l}</li>)}
                </ul>
              </div>
              <button className="btn btn-light" onClick={() => startCoaching(selectedScenario, selectedSide)}>
                <Play size={18} /> Gespräch starten
              </button>
              <p className="stage-hint">Mikrofon und Kamera werden beim Start abgefragt.</p>
            </aside>
          )}
        </div>
      </>
    )
  }

  const scenario = session.scenario
  const side = session.practiceSide
  const persona = side ? personaFor(side.id, side.avatar_role) : { name: 'Dein Gegenüber', role: '', mood: '' }

  // ---- CREATING ----
  if (session.status === 'creating') {
    return (
      <div className="call-layout">
        <div className="stage stage--call stage--connecting">
          <div className="stage-person">
            <Portrait persona={persona} ringing />
            <h3>{persona.name}</h3>
            <p className="stage-role">Verbindung wird aufgebaut …</p>
          </div>
        </div>
        <CallSidebar scenario={scenario} side={side} persona={persona} />
      </div>
    )
  }

  // ---- ACTIVE COACHING ----
  if (inCall && session.embedUrl) {
    return (
      <div className="call-layout">
        <div className="stage stage--call">
          <iframe
            src={session.embedUrl}
            allow="microphone; camera; autoplay; fullscreen; display-capture"
            title={`Video-Gespräch mit ${persona.name}`}
            className="call-frame"
          />
          <div className="call-overlay-top">
            <span className="stage-chip stage-chip--live"><span className="dot" /> Live {elapsed}</span>
            <span className="stage-chip">{scenario?.title}</span>
          </div>
          {session.status === 'analyzing' && (
            <div className="call-analyzing">
              <Loader2 className="spin" size={30} />
              <p>Gespräch wird ausgewertet …</p>
            </div>
          )}
        </div>
        <CallSidebar scenario={scenario} side={side} persona={persona}>
          <button className="btn btn-primary" onClick={stopAndAnalyze} disabled={session.status === 'analyzing'}>
            {session.status === 'analyzing'
              ? <><Loader2 className="spin" size={18} /> Wird ausgewertet …</>
              : <><PhoneOff size={18} /> Beenden und auswerten</>}
          </button>
          <p className="sidebar-note">
            Verabschiedet ihr euch, legt {persona.name} selbst auf und die Auswertung startet automatisch.
          </p>
        </CallSidebar>
      </div>
    )
  }

  // ---- ANALYSIS RESULT ----
  if (session.status === 'done') {
    const labels = rubricLabels(scenario)
    return (
      <div className="result">
        <header className="result-head">
          <div className="result-title">
            <Portrait persona={persona} size="sm" />
            <div>
              <h1>Deine Auswertung</h1>
              <p>{scenario?.title} mit {persona.name}</p>
            </div>
          </div>
          <div className="result-actions">
            {scenario && side && (
              <button className="btn btn-secondary" onClick={() => startCoaching(scenario, side)}>
                <RotateCcw size={18} /> Noch einmal üben
              </button>
            )}
            <button className="btn btn-primary" onClick={reset}>
              <Play size={18} /> Neue Situation
            </button>
          </div>
        </header>

        {analysis?.error && <div className="notice notice--error">{analysis.error}</div>}
        {analysis?.note && <div className="notice">{analysis.note}</div>}

        {!analysis?.error && (
          <>
            <div className="score-grid">
              <ScoreCard label={labels[0]} score={analysis?.empathy_score || 0} feedback={analysis?.empathy_feedback || ''} />
              <ScoreCard label={labels[1]} score={analysis?.clarity_score || 0} feedback={analysis?.clarity_feedback || ''} />
              <ScoreCard label={labels[2]} score={analysis?.result_score || 0} feedback={analysis?.result_feedback || ''} />
            </div>

            <div className="result-columns">
              <section className="panel glass">
                <h2>Zusammenfassung</h2>
                <p>{analysis?.summary}</p>
              </section>
              {analysis?.counterpart_journey && (
                <section className="panel glass">
                  <h2>So hat {persona.name} das Gespräch erlebt</h2>
                  <p>{analysis.counterpart_journey}</p>
                </section>
              )}
            </div>

            {analysis?.better_phrasings && analysis.better_phrasings.length > 0 && (
              <section className="panel glass">
                <h2>Bessere Formulierungen</h2>
                <ol className="phrasings">
                  {analysis.better_phrasings.map((p, i) => (
                    <li key={i}>
                      <div className="phrase phrase--said">
                        <span>Gesagt</span>
                        <p>„{p.original}“</p>
                      </div>
                      <div className="phrase phrase--better">
                        <span>Besser</span>
                        <p>„{p.better}“</p>
                      </div>
                      {p.why && <p className="phrase-why">{p.why}</p>}
                    </li>
                  ))}
                </ol>
              </section>
            )}

            {analysis?.asr_notes && analysis.asr_notes.length > 0 && (
              <div className="notice">
                <strong>Vermutlich falsch erkannt, nicht bewertet:</strong> {analysis.asr_notes.join(', ')}
              </div>
            )}

            {analysis?.transcript && (
              <details className="transcript glass">
                <summary>Transkript anzeigen</summary>
                <pre>{analysis.transcript}</pre>
              </details>
            )}
          </>
        )}
      </div>
    )
  }

  // ---- ERROR ----
  if (session.status === 'error') {
    return (
      <section className="state-card glass">
        <AlertCircle size={28} />
        <h2>Das Gespräch konnte nicht starten</h2>
        <p>{session.error || 'Unbekannter Fehler'}</p>
        <button className="btn btn-secondary" onClick={reset}>Zurück zur Auswahl</button>
      </section>
    )
  }

  return null
}

function CallSidebar({ scenario, side, persona, children }: {
  scenario?: Scenario
  side?: PracticeSide
  persona: Persona
  children?: React.ReactNode
}) {
  return (
    <aside className="call-sidebar glass">
      <div className="sidebar-person">
        <Portrait persona={persona} size="sm" />
        <div>
          <strong>{persona.name}</strong>
          <span>{persona.role}</span>
        </div>
      </div>
      {side && (
        <div className="sidebar-block">
          <h4>Dein Ziel</h4>
          <p>{side.user_goal}</p>
        </div>
      )}
      <div className="sidebar-block">
        <h4>Bewertet wird</h4>
        <ul className="criteria criteria--light">
          {rubricLabels(scenario).map(l => <li key={l}>{l}</li>)}
        </ul>
      </div>
      <div className="sidebar-block">
        <h4>Tipp</h4>
        <p>Sprich so, wie du es im echten Gespräch tun würdest. {persona.name} bleibt durchgehend in der Rolle.</p>
      </div>
      {children}
    </aside>
  )
}
