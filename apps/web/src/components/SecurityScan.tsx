import { AlertTriangle, ShieldCheck } from "lucide-react";
import type { GitSecurityScan } from "../types";

export function SecurityScan({ scan, onContinue }: { scan: GitSecurityScan | null; onContinue: () => void }) {
  const hasRisk = Boolean(scan?.blocked_files?.length || scan?.secret_matches?.length || scan?.large_files?.length);
  return <div className={`security-box ${hasRisk ? "risk" : ""}`}><div className="widget-title">{hasRisk ? <AlertTriangle size={16} /> : <ShieldCheck size={16} />}<strong>推送前安全检查</strong></div><p>安全文件： {scan?.safe_files?.length ?? 0}</p>{(scan?.blocked_files?.length ?? 0) > 0 && <p>已拦截： {scan?.blocked_files?.slice(0, 8).join(", ")}</p>}{(scan?.large_files?.length ?? 0) > 0 && <p>大文件： {scan?.large_files?.map((item) => item.path).slice(0, 5).join(", ")}</p>}{(scan?.secret_matches?.length ?? 0) > 0 && <p>疑似密钥： {scan?.secret_matches?.map((item) => item.path).slice(0, 5).join(", ")}</p>}{hasRisk && <button onClick={onContinue}>仅使用安全文件继续</button>}</div>;
}
