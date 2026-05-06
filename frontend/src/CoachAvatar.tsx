import { useState, useEffect, useCallback, useRef } from 'react'
import { StopCircle, Loader2, AlertCircle, CheckCircle2, RefreshCw, Grid3X3, ChevronDown } from 'lucide-react'

interface Scenario {
  id: string
  title: string
  category: string
  icon: string
  description: string
  avatar_role: string
  user_goal: string
}

interface SessionState {
  status: 'idle' | 'selecting' | 'creating' | 'active' | 'analyzing' | 'done' | 'error'
  embedUrl?: string
  sessionId?: string
  scenario?: Scenario
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
  error?: string
  note?: string
}

export default function CoachAvatar() {
  const [session, setSession] = useState<SessionState>({ status: 'selecting' })
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [setupStatus, setSetupStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    fetch('/api/scenarios')
      .then(r => r.json())
      .then(data => setScenarios(data.scenarios || []))
      .catch(() => {})

    fetch('/api/session/status')
      .then(r => r.json())
      .then(data => {
        if (!data.configured) {
          return fetch('/api/heygen/setup')
        }
        return { ok: true }
      })
      .then(() => setSetupStatus('ready'))
      .catch(() => setSetupStatus('error'))
  }, [])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        menuRef.current && !menuRef.current.contains(e.target as Node) &&
        triggerRef.current && !triggerRef.current.contains(e.target as Node)
      ) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) {
      document.addEventListener('mousedown', handleClick)
      return () => document.removeEventListener('mousedown', handleClick)
    }
  }, [menuOpen])

  const startCoaching = useCallback(async (scenario: Scenario) => {
    setMenuOpen(false)
    setSession({ status: 'creating', scenario })
    setAnalysis(null)
    try {
      const resp = await fetch(`/api/session/create?scenario_id=${scenario.id}&sandbox=false`, { method: 'POST' })
      const data = await resp.json()

      if (data.error) {
        setSession({ status: 'error', error: data.error, scenario })
        return
      }

      setSession({
        status: 'active',
        embedUrl: data.embed_url,
        sessionId: data.session_id,
        scenario
      })
    } catch (err: any) {
      setSession({ status: 'error', error: err.message || 'Fehler bei Session-Erstellung', scenario })
    }
  }, [])

  const stopAndAnalyze = useCallback(async () => {
    if (!session.sessionId) return
    setSession(s => ({ ...s, status: 'analyzing' }))

    try {
      const formData = new FormData()
      formData.append('session_id', session.sessionId)
      const resp = await fetch(`/api/session/analyze?session_id=${session.sessionId}&scenario_id=${session.scenario?.id || 'free'}`, { method: 'POST' })
      const result = await resp.json()
      setAnalysis(result)
      setSession(s => ({ ...s, status: 'done' }))
    } catch (err: any) {
      setAnalysis({ error: err.message } as Analysis)
      setSession(s => ({ ...s, status: 'done' }))
    }
  }, [session.sessionId])

  const reset = useCallback(() => {
    setSession({ status: 'selecting' })
    setAnalysis(null)
  }, [])

  if (setupStatus === 'loading') {
    return (
      <div className="coach-container">
        <div className="coach-placeholder">
          <Loader2 className="spinner-icon" size={48} />
          <h2>Coach wird vorbereitet...</h2>
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
          <p>Der Coach konnte nicht initialisiert werden.</p>
          <button onClick={() => window.location.reload()}>Neu laden</button>
        </div>
      </div>
    )
  }

  // ---- SCENARIO SELECTION ----
  if (session.status === 'selecting') {
    const categories = [...new Set(scenarios.map(s => s.category))]
    return (
      <div className="coach-container">
        <div className="coach-placeholder" style={{ borderStyle: 'solid', background: 'var(--surface-inset)' }}>
          <Grid3X3 size={40} />
          <h2>Trainingsszenario wählen</h2>
          <p>Wähle eine Gesprächssituation — der Avatar spielt die Rolle deines Gegenübers. Nach dem Gespräch erhältst du eine detaillierte Analyse.</p>
          <div style={{ position: 'relative', marginTop: 8 }}>
            <button
              ref={triggerRef}
              className="coach-start-btn"
              onClick={() => setMenuOpen(o => !o)}
            >
              Szenario auswählen <ChevronDown size={14} style={{ transition: 'transform .15s', transform: menuOpen ? 'rotate(180deg)' : 'rotate(0)' }} />
            </button>
            {menuOpen && (
              <div ref={menuRef} className="scenario-dropdown">
                {categories.map(cat => (
                  <div key={cat}>
                    <div className="dropdown-category">{cat}</div>
                    {scenarios.filter(s => s.category === cat).map(s => (
                      <button
                        key={s.id}
                        className="dropdown-item"
                        onClick={() => startCoaching(s)}
                      >
                        {s.title}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
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
          <h2>Session wird erstellt...</h2>
          <p>Szenario: {session.scenario?.title}</p>
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
                🎯 Ziel: {session.scenario?.user_goal}
                <br />
                💡 Der Avatar ist bereits in seiner Rolle. Sprich einfach natürlich — wie im echten Leben.
              </p>
            </div>
            <button
              className="coach-stop-btn"
              onClick={stopAndAnalyze}
              disabled={session.status === 'analyzing'}
            >
              {session.status === 'analyzing'
                ? <><Loader2 className="spinner-icon" size={18} /> Analysiere...</>
                : <><StopCircle size={18} /> Beenden & Analysieren</>
              }
            </button>
          </div>
          <div className="coach-iframe-wrapper">
            <iframe
              src={session.embedUrl}
              allow="microphone; camera"
              title="LiveAvatar Coach"
              className="coach-iframe"
            />
          </div>
          <div className="coach-tips">
            <p>
              <strong>Tipp:</strong> Erlaube Mikrofon-Zugriff. Der Avatar ist bereits in der richtigen Rolle — sprich einfach
              natürlich, wie du es im echten Leben tun würdest. Klicke "Beenden &amp; Analysieren", wenn das Gespräch fertig ist.
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
              <small>Hinweis: {analysis.error}</small>
            </div>
          )}

          {analysis?.note && (
            <div className="coach-tips" style={{ marginBottom: 16 }}>
              <p>💡 {analysis.note}</p>
            </div>
          )}

          {!analysis?.error && (
            <>
              <div className="scores-grid">
                <ScoreBar label="Empathie" score={analysis?.empathy_score || 0} feedback={analysis?.empathy_feedback || ''} />
                <ScoreBar label="Klarheit" score={analysis?.clarity_score || 0} feedback={analysis?.clarity_feedback || ''} />
                <ScoreBar label="Ergebnis" score={analysis?.result_score || 0} feedback={analysis?.result_feedback || ''} />
              </div>

              <div className="summary-section">
                <h3>Zusammenfassung</h3>
                <p>{analysis?.summary}</p>
              </div>

              {analysis?.transcript && (
                <details style={{ marginTop: 16 }}>
                  <summary style={{ cursor: 'pointer', color: 'var(--secondary-text)' }}>Transkript anzeigen</summary>
                  <pre className="transcript-pre">{analysis.transcript}</pre>
                </details>
              )}
            </>
          )}

          <div style={{ textAlign: 'center', marginTop: 24, display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button onClick={reset}>
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

function ScoreBar({ label, score, feedback }: { label: string, score: number, feedback: string }) {
  return (
    <div className="score-item">
      <div className="score-header">
        <span>{label}</span>
        <span className="score-value">{score}/10</span>
      </div>
      <div className="progress-bg">
        <div className="progress-fill" style={{ width: `${score * 10}%` }}></div>
      </div>
      <p className="score-feedback">{feedback}</p>
    </div>
  )
}
