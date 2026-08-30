export function ProgressLine({ label, value }: { label: string; value: number }) {
  return <div className="progress-line"><div><span>{label}</span><strong>{Math.round(value)}%</strong></div><progress value={value} max={100} /></div>;
}
