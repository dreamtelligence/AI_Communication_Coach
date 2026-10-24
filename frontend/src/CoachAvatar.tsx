import { useState, useEffect, useCallback, useRef } from 'react'
import { StopCircle, Loader2, AlertCircle, CheckCircle2, RefreshCw, Grid3X3, PlayCircle } from 'lucide-react'
import RadialGauge from '@/components/RadialGauge'

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

interface Analysis {
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

export default function CoachAvatar() {
  const [session, setSession] = useState<SessionState>({ status: 'selecting' })
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = useState('salary')
  const [selectedSideId, setSelectedSideId] = useState('')
  const [setupStatus, setSetupStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)

  useEffect(() => {
    fetch('/api/scenarios')
      .then(r => r.json())
      .then(data => setScenarios(data.scenarios || []))
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

  const reset = useCallback(() => {
    setSession({ status: 'selecting' })
    setAnalysis(null)
  }, [])

  if (setupStatus === 'loading') {
    return (
      <div className="coach-container">
        <div className="coach-placeholder">
          <Loader2 className="spinner-icon" size={48} />
          <h2>Coach wird vorbereitet…</h2>
          <p>Die KI-Ressourcen werden initialisiert.</p>
        </div>
      </div>
    )
  }

  if (setupStatus === 'error') {
    return (
      <div className="coach-container">
        <div className="coach-placeholder coach-error">
          <AlertCircle size={48} />
          <h2>Setup-Fehler</h2>
          <p>Tavus ist nicht konfiguriert oder aktuell nicht erreichbar.</p>
          <button onClick={() => window.location.reload()}>Neu laden</button>
        </div>
      </div>
    )
  }

  // ---- SCENARIO SELECTION ----
  if (session.status === 'selecting') {
    const selectedScenario = scenarios.find(s => s.id === selectedScenarioId) || scenarios[0]
    const selectedSide = selectedScenario?.practice_sides.find(side => side.id === selectedSideId) || selectedScenario?.practice_sides[0]
    return (
      <div className="coach-container">
        <div className="coach-placeholder" style={{ borderStyle: 'solid' }}>
          <Grid3X3 size={40} />
          <h2>Demo-Szenario wählen</h2>
          <p>Wähle eines der zwei fokussierten Trainings und danach die Rolle, die du selbst üben möchtest.</p>

          <div className="demo-scenario-grid">
            {scenarios.map(s => (
              <button
                key={s.id}
                className={`scenario-choice ${selectedScenario?.id === s.id ? 'active' : ''}`}
                onClick={() => {
                  setSelectedScenarioId(s.id)
                  setSelectedSideId(s.practice_sides[0]?.id || '')
                }}
              >
                <strong>{s.title}</strong>
                <span>{s.description}</span>
              </button>
            ))}
          </div>

          {selectedScenario && selectedSide && (
            <div className="role-panel">
              <div className="role-panel-title">Welche Seite möchtest du trainieren?</div>
              <div className="role-options">
                {selectedScenario.practice_sides.map(side => (
                  <button
                    key={side.id}
                    className={`role-option ${selectedSide.id === side.id ? 'active' : ''}`}
                    onClick={() => setSelectedSideId(side.id)}
                  >
                    <strong>{side.label}</strong>
                    <span>{side.user_goal}</span>
                  </button>
                ))}
              </div>
              <button
                className="coach-start-btn"
                onClick={() => startCoaching(selectedScenario, selectedSide)}
              >
                <PlayCircle size={18} /> Training starten
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ---- CREATING ----
  if (session.status === 'creating') {
    return (
      <div className="coach-container">
        <div className="coach-placeholder">
          <Loader2 className="spinner-icon" size={48} />
          <h2>Session wird erstellt…</h2>
          <p>Szenario: {session.scenario?.title}</p>
          <p>Trainierte Rolle: {session.practiceSide?.label}</p>
        </div>
      </div>
    )
  }

  // ---- ACTIVE COACHING ----
  if ((session.status === 'active' || session.status === 'analyzing') && session.embedUrl) {
    return (
      <div className="coach-container">
        <div className="coach-active">
          <div className="coach-header">
            <div>
              <h2>
                <span className="live-dot"></span>
                {session.scenario?.title || 'Live Coaching'}
              </h2>
              <p className="coach-scenario-hint">
                Ziel: {session.practiceSide?.user_goal}
                <br />
                Deine Rolle: {session.practiceSide?.label}. Der Avatar spielt konsequent die Gegenseite.
              </p>
            </div>
            <button
              className="coach-stop-btn"
              onClick={stopAndAnalyze}
              disabled={session.status === 'analyzing'}
            >
              {session.status === 'analyzing'
                ? <><Loader2 className="spinner-icon" size={18} /> Analysiere…</>
                : <><StopCircle size={18} /> Beenden & Analysieren</>
              }
            </button>
          </div>
          <div className="coach-iframe-wrapper">
            <iframe
              src={session.embedUrl}
              allow="microphone; camera; autoplay; fullscreen; display-capture"
              title="Tavus Coach"
              className="coach-iframe"
            />
          </div>
          <div className="coach-tips">
            <p>
              <strong>Tipp:</strong> Erlaube Mikrofon-Zugriff. Der Avatar ist bereits in der richtigen Rolle — sprich einfach
              natürlich, wie du es im echten Leben tun würdest. Verabschiedet ihr euch, legt der Avatar auf und die Analyse startet automatisch. Du kannst auch jederzeit "Beenden & Analysieren" klicken.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // ---- ANALYSIS RESULT ----
  if (session.status === 'done') {
    return (
      <div className="coach-container">
        <div className="analysis-result">
          <div className="result-header">
            <CheckCircle2 size={24} /> Coaching-Analyse: {session.scenario?.title}
          </div>

          {analysis?.error && (
            <div className="debug-info">
              Hinweis: {analysis.error}
            </div>
          )}

          {analysis?.note && (
            <div className="coach-tips" style={{ marginBottom: 20 }}>
              <p>{analysis.note}</p>
            </div>
          )}

          {!analysis?.error && (
            <>
              <div className="gauges-row">
                <RadialGauge label="Empathie" score={analysis?.empathy_score || 0} feedback={analysis?.empathy_feedback || ''} />
                <RadialGauge label="Klarheit" score={analysis?.clarity_score || 0} feedback={analysis?.clarity_feedback || ''} />
                <RadialGauge label="Ergebnis" score={analysis?.result_score || 0} feedback={analysis?.result_feedback || ''} />
              </div>

              <div className="summary-section">
                <h3>Zusammenfassung</h3>
                <p>{analysis?.summary}</p>
              </div>

              {analysis?.counterpart_journey && (
                <div className="summary-section">
                  <h3>Verlauf beim Gegenüber</h3>
                  <p>{analysis.counterpart_journey}</p>
                </div>
              )}

              {analysis?.better_phrasings && analysis.better_phrasings.length > 0 && (
                <div className="summary-section">
                  <h3>So hätten Sie es sagen können</h3>
                  {analysis.better_phrasings.map((p, i) => (
                    <div key={i} style={{ marginBottom: 14 }}>
                      <p style={{ color: 'var(--text-secondary)', textDecoration: 'line-through' }}>„{p.original}“</p>
                      <p><strong>„{p.better}“</strong></p>
                      {p.why && <p style={{ color: 'var(--text-secondary)', fontSize: '0.9em' }}>{p.why}</p>}
                    </div>
                  ))}
                </div>
              )}

              {analysis?.asr_notes && analysis.asr_notes.length > 0 && (
                <div className="coach-tips" style={{ marginTop: 16 }}>
                  <p>
                    <strong>Vermutlich falsch erkannt (nicht bewertet):</strong>{' '}
                    {analysis.asr_notes.join(' · ')}
                  </p>
                </div>
              )}

              {analysis?.transcript && (
                <details style={{ marginTop: 20 }}>
                  <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)', fontWeight: 500 }}>Transkript anzeigen</summary>
                  <pre className="transcript-pre">{analysis.transcript}</pre>
                </details>
              )}
            </>
          )}

          <div style={{ textAlign: 'center', marginTop: 28, display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button onClick={reset} className="btn-accent">
              <RefreshCw size={18} /> Neues Szenario
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ---- ERROR ----
  if (session.status === 'error') {
    return (
      <div className="coach-container">
        <div className="coach-placeholder coach-error">
          <AlertCircle size={48} />
          <h2>Fehler</h2>
          <p>{session.error || 'Unbekannter Fehler'}</p>
          <button onClick={reset}>Zurück zur Auswahl</button>
        </div>
      </div>
    )
  }

  return null
}
