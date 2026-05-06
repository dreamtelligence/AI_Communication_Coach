interface RadialGaugeProps {
  label: string;
  score: number;
  feedback: string;
}

const clamp = (v: number) => Math.max(0, Math.min(10, v));
const circumference = 2 * Math.PI * 36; // r=36

function fillClass(score: number): string {
  if (score >= 7) return 'fill--success';
  if (score >= 4) return 'fill--warning';
  return 'fill--danger';
}

export default function RadialGauge({ label, score, feedback }: RadialGaugeProps) {
  const s = clamp(score);
  const offset = circumference * (1 - s / 10);

  return (
    <div className="gauge-card">
      <div className="gauge-label">{label}</div>
      <div className="gauge-ring">
        <svg viewBox="0 0 84 84">
          <circle className="track" cx="42" cy="42" r="36" />
          <circle
            className={`fill ${fillClass(s)}`}
            cx="42" cy="42" r="36"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="gauge-value">{s}<span style={{fontSize:'0.65em',fontWeight:500,color:'var(--text-tertiary)'}}>/10</span></div>
      </div>
      <p className="gauge-feedback">{feedback}</p>
    </div>
  );
}
