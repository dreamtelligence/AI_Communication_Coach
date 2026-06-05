import { useState, useRef } from 'react'
import { Upload, FileAudio, CheckCircle2, AlertCircle, MessageCircle, Mic } from 'lucide-react'
import CoachAvatar from './CoachAvatar'
import { PageBackground } from '@/components/ui/background-components'
import RadialGauge from '@/components/RadialGauge'

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

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.error || data.detail || `Upload failed: ${response.statusText}`)
      }
      setTranscript(data.text)
      setAnalysis(data.analysis)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred during transcription.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageBackground>
    <div className="dashboard">
      <header>
        <h1>CoachVoice</h1>
        <p className="subtitle">AI Communication Coach — Real-Time Analysis</p>
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
              <p>Drop an audio file or click to browse</p>
            )}
          </div>

          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <button
              className={file && !loading ? 'btn-accent' : ''}
              onClick={handleUpload}
              disabled={!file || loading}
            >
              {loading ? 'Processing...' : 'Start AI Analysis'}
            </button>
          </div>

          {loading && (
            <div className="loading-container">
              <div className="spinner"></div>
              <p style={{ color: 'var(--text-secondary)' }}>AI is transcribing & analyzing on Modal L40S GPU…</p>
            </div>
          )}

          {error && (
            <div className="result-card" style={{ borderColor: 'rgba(248,113,113,0.3)' }}>
              <div className="result-header" style={{ color: 'var(--danger)' }}>
                <AlertCircle size={20} /> Error
              </div>
              <p className="transcript-text">{error}</p>
            </div>
          )}

          {analysis && (
            <div className="result-card">
              <div className="result-header">
                <CheckCircle2 size={20} /> Coaching Analysis
              </div>

              <div className="gauges-row">
                <RadialGauge label="Empathie" score={analysis.empathy_score} feedback={analysis.empathy_feedback} />
                <RadialGauge label="Klarheit" score={analysis.clarity_score} feedback={analysis.clarity_feedback} />
                <RadialGauge label="Ergebnis" score={analysis.result_score} feedback={analysis.result_feedback} />
              </div>

              <div className="summary-section">
                <h3>Zusammenfassung</h3>
                <p>{analysis.summary}</p>
              </div>

              {analysis.error && (
                <div className="debug-info">
                  Analysis Note: {analysis.error}
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

      <footer>
        Powered by Tavus, Modal & NVIDIA Parakeet
      </footer>
    </div>
    </PageBackground>
  )
}

export default App
