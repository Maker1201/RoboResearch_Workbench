export function PathInput({ label, value, onChange, password = false }: { label: string; value: string; onChange: (value: string) => void; password?: boolean }) {
  return <label className="field-label"><span>{label}</span><input type={password ? "password" : "text"} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}
