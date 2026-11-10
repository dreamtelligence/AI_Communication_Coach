interface ScoreCardProps {
  label: string
  score: number | null
  feedback: string
}

const clamp = (v: number) => Math.max(0, Math.min(10, v))

export default function ScoreCard({ label, score, feedback }: ScoreCardProps) {
  const s = score === null ? null : clamp(score)
  return (
    <div className="score-card glass">
      <div className="score-head">
        <span className="score-label">{label}</span>
        <span className="score-value">{s === null ? '–' : <>{s}<small>/10</small></>}</span>
      </div>
      {s === null ? <p>Nicht beurteilbar</p> : (
        <div className="score-track" role="meter" aria-valuemin={0} aria-valuemax={10} aria-valuenow={s} aria-label={label}>
          <span style={{ width: `${s * 10}%` }} />
        </div>
      )}
      <p className="score-feedback">{feedback}</p>
    </div>
  )
}
