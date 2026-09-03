export function PathInput({ label, value, onChange, password = false, placeholder, hint }: { label: string; value: string; onChange: (value: string) => void; password?: boolean; placeholder?: string; hint?: string }) {
  return <label className="field-label"><span>{label}</span><input type={password ? "password" : "text"} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />{hint && <small className="field-hint">{hint}</small>}</label>;
}
