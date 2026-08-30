import type { ReactNode } from "react";

export function WidgetTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return <div className="widget-title">{icon}<strong>{title}</strong></div>;
}
