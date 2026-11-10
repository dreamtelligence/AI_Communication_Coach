import { useState, useRef } from 'react'
import { AlertCircle, ArrowUpRight, AudioLines, FileAudio, Loader2, Upload, Video } from 'lucide-react'
import CoachAvatar from './CoachAvatar'
import ScoreCard from '@/components/ScoreCard'

interface AnalysisResult {
  empathy_score: number;
  empathy_feedback: string;
  clarity_score: number;
  clarity_feedback: string;
  result_score: number;
  result_feedback: string;
  summary: string;
  error?: string;
}

type Tab = 'live' | 'upload'

const SITE_URL = 'https://dreamtelligence.de'
const SERVICE_URL = `${SITE_URL}/leistungen/ki-gespraechstraining`

function PageBackground() {
  return (
    <div className="sky" aria-hidden="true">
      <div className="sky-gradient" />
      <img className="sky-cloud" src="/brand/hero-wolke.webp" alt="" />
      <div className="sky-ray sky-ray--left" />
      <div className="sky-ray sky-ray--right" />
      <div className="sky-fade" />
    </div>
  )
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('live')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const pickFile = (picked: File) => {
    setFile(picked)
    setTranscript(null)
    setAnalysis(null)
    setError(null)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) pickFile(e.target.files[0])
  }

  const handleUpload = async () => {
    if (!file) return

    setLoading(true)
    setError(null)
    setTranscript(null)
    setAnalysis(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.error || data.detail || `Upload fehlgeschlagen: ${response.statusText}`)
      }
      setTranscript(data.text)
      setAnalysis(data.analysis)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Die Aufnahme konnte nicht ausgewertet werden.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageBackground />

      <div className="nav-frame">
        <header className="nav">
          <a className="nav-logo" href={SITE_URL} aria-label="Dreamtelligence Startseite">
            <img src="/brand/logo.png" alt="Dreamtelligence" width={192} height={192} />
          </a>
          <span className="nav-sep" aria-hidden="true" />
          <nav className="nav-tabs" aria-label="Bereiche">
            <button className={`nav-tab ${activeTab === 'live' ? 'is-active' : ''}`} aria-current={activeTab === 'live'} onClick={() => setActiveTab('live')}>
              <Video size={16} /> Live-Training
            </button>
            <button className={`nav-tab ${activeTab === 'upload' ? 'is-active' : ''}`} aria-current={activeTab === 'upload'} onClick={() => setActiveTab('upload')}>
              <AudioLines size={16} /> Audio-Analyse
            </button>
          </nav>
          <a className="nav-site" href={SERVICE_URL}>
            Zur Leistung <ArrowUpRight size={16} />
          </a>
        </header>
      </div>

      <main className="page">
        {activeTab === 'live' && <CoachAvatar />}

        {activeTab === 'upload' && (
          <>
            <header className="page-intro">
              <h1>Englische Aufnahme auswerten.</h1>
              <p>
                Lade eine englischsprachige Übungsaufnahme mit einer sprechenden Person hoch.
                Sie wird abgeschrieben und nach Empathie, Klarheit und Ergebnis bewertet.
              </p>
            </header>

            <div className="upload">
              <div
                className={`dropzone glass ${file ? 'has-file' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click() } }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) pickFile(e.dataTransfer.files[0])
                }}
              >
                <input type="file" ref={fileInputRef} onChange={handleFileChange} accept="audio/*" hidden />
                <span className="icon-box">{file ? <FileAudio size={22} strokeWidth={1.6} /> : <Upload size={22} strokeWidth={1.6} />}</span>
                {file ? (
                  <p><strong>{file.name}</strong><span>Andere Datei wählen</span></p>
                ) : (
                  <p><strong>Audiodatei hierher ziehen</strong><span>oder klicken, um eine Datei auszuwählen</span></p>
                )}
              </div>

              <button className="btn btn-primary" onClick={handleUpload} disabled={!file || loading}>
                {loading ? <><Loader2 className="spin" size={18} /> Wird ausgewertet …</> : 'Aufnahme auswerten'}
              </button>

              {error && (
                <div className="notice notice--error"><AlertCircle size={18} /> {error}</div>
              )}
            </div>

            {analysis && (
              <div className="result">
                <div className="score-grid">
                  <ScoreCard label="Empathie" score={analysis.empathy_score} feedback={analysis.empathy_feedback} />
                  <ScoreCard label="Klarheit" score={analysis.clarity_score} feedback={analysis.clarity_feedback} />
                  <ScoreCard label="Ergebnis" score={analysis.result_score} feedback={analysis.result_feedback} />
                </div>
                <section className="panel glass">
                  <h2>Zusammenfassung</h2>
                  <p>{analysis.summary}</p>
                </section>
                {analysis.error && <div className="notice">{analysis.error}</div>}
              </div>
            )}

            {transcript && (
              <details className="transcript glass result" open>
                <summary>Transkript</summary>
                <pre>{transcript}</pre>
              </details>
            )}
          </>
        )}
      </main>

      <footer className="footer">
        <span>KI-Gesprächstraining von <a href={SITE_URL}>Dreamtelligence</a></span>
        <span>Live-Avatar: Tavus</span>
      </footer>
    </>
  )
}

export default App
