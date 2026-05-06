import { cn } from "@/lib/utils";

export function PageBackground({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen w-full relative bg-white">
      <div
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `
            radial-gradient(circle at center, #FFF991 0%, transparent 70%)
          `,
          opacity: 0.6,
          mixBlendMode: "multiply",
        }}
      />
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}
