import type { ReactNode } from "react";

export function IntegrationPanel({ title, enabled, onEnabled, onTest, testLabel, enabledLabel, children }: {
  title: string;
  enabled: boolean;
  onEnabled: (enabled: boolean) => void;
  onTest: () => void;
  testLabel: string;
  enabledLabel: string;
  children: ReactNode;
}) {
  return <article className="integration-panel">
    <div className="panel-heading compact-heading">
      <h3>{title}</h3>
      <button onClick={onTest}>{testLabel}</button>
    </div>
    <label className="checkbox-line"><input type="checkbox" checked={enabled} onChange={(event) => onEnabled(event.target.checked)} />{enabledLabel}</label>
    <div className="form-grid">{children}</div>
  </article>;
}
