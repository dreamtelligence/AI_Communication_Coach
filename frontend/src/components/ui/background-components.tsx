export function PageBackground({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen w-full relative" style={{ background: 'var(--bg)' }}>
      {/* Animated mesh gradient blobs */}
      <div className="mesh-bg">
        <div className="mesh-blob mesh-blob--1" />
        <div className="mesh-blob mesh-blob--2" />
        <div className="mesh-blob mesh-blob--3" />
      </div>

      {/* Subtle noise texture overlay */}
      <div className="mesh-noise" />

      {/* Content */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </div>
    </div>
  );
}
