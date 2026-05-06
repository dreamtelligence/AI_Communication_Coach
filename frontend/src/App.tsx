import { useState, useRef } from 'react'
import { Upload, FileAudio, CheckCircle2, AlertCircle, MessageCircle, Mic } from 'lucide-react'
import CoachAvatar from './CoachAvatar'
import { PageBackground } from '@/components/ui/background-components'

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

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('live')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setTranscript(null)
      setAnalysis(null)
      setError(null)
    }
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

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`)
      }

      const data = await response.json()
      setTranscript(data.text)
      setAnalysis(data.analysis)
    } catch (err: any) {
      setError(err.message || 'An error occurred during transcription.')
    } finally {
      setLoading(false)
    }
  }

  const ScoreBar = ({ label, score, feedback }: { label: string, score: number, feedback: string }) => (
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

  return (
    <PageBackground>
    <div className="dashboard">
      <header>
        <h1>CoachVoice</h1>
        <p className="subtitle">AI Communication Coach &amp; Real-Time Analysis</p>
      </header>

      <div className="tab-bar">
        <button
          className={`tab-btn ${activeTab === 'live' ? 'active' : ''}`}
          onClick={() => setActiveTab('live')}
        >
          <MessageCircle size={18} /> Live Coaching
        </button>
        <button
          className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          <Mic size={18} /> Audio-Analyse
        </button>
      </div>

      {activeTab === 'live' && (
        <CoachAvatar />
      )}

      {activeTab === 'upload' && (
        <>
          <div
            className="dropzone"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                setFile(e.dataTransfer.files[0])
                setTranscript(null)
                setAnalysis(null)
                setError(null)
              }
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="audio/*"
            />
            <Upload className="upload-icon" />
            {file ? (
              <p>Selected: <strong>{file.name}</strong></p>
            ) : (
              <p>Click or drag audio file here to analyze</p>
            )}
          </div>

          <div style={{ textAlign: 'center' }}>
            <button
              onClick={handleUpload}
              disabled={!file || loading}
            >
              {loading ? 'Processing...' : 'Start AI Analysis'}
            </button>
          </div>

          {loading && (
            <div className="loading-container">
              <div className="spinner"></div>
              <p>AI is transcribing &amp; analyzing on Modal L40S GPU...</p>
            </div>
          )}

          {error && (
            <div className="result-card" style={{ borderColor: '#f85149' }}>
              <div className="result-header" style={{ color: '#f85149' }}>
                <AlertCircle size={20} /> Error
              </div>
              <p className="transcript-text">{error}</p>
            </div>
          )}

          {analysis && (
            <div className="result-card analysis-card">
              <div className="result-header">
                <CheckCircle2 size={20} /> Coaching Analysis
              </div>

              <div className="scores-grid">
                <ScoreBar label="Empathie" score={analysis.empathy_score} feedback={analysis.empathy_feedback} />
                <ScoreBar label="Klarheit" score={analysis.clarity_score} feedback={analysis.clarity_feedback} />
                <ScoreBar label="Ergebnis" score={analysis.result_score} feedback={analysis.result_feedback} />
              </div>

              <div className="summary-section">
                <h3>Zusammenfassung</h3>
                <p>{analysis.summary}</p>
              </div>

              {analysis.error && (
                <div className="debug-info">
                  <small>Analysis Note: {analysis.error}</small>
                </div>
              )}
            </div>
          )}

          {transcript && (
            <div className="result-card">
              <div className="result-header">
                <FileAudio size={20} /> Transcript
              </div>
              <div className="transcript-text">{transcript}</div>
            </div>
          )}
        </>
      )}

      <footer style={{ marginTop: '40px', fontSize: '0.8rem', color: 'var(--secondary-text)', textAlign: 'center' }}>
        Powered by HeyGen LiveAvatar, Modal &amp; NVIDIA Parakeet
      </footer>
    </div>
    </PageBackground>
  )
}

export default App
