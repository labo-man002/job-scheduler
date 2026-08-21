export function StatusBadge({ fill, label, pulse = false }: { fill: string; label: string; pulse?: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: `${fill}1a`, color: fill }}
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${pulse ? "status-pulse" : ""}`}
        style={{ backgroundColor: fill, "--pulse-color": fill } as React.CSSProperties}
      />
      {label}
    </span>
  );
}
