import { useState } from "react";
import { getLog, listLogs } from "../../api/endpoints";
import type { RequestLogDetail } from "../../api/types";
import { useAsync } from "../../hooks/useAsync";
import Modal from "../../components/Modal";

export function LogTable({
  logs,
  onOpen,
}: {
  logs: { id: number; created_at: string; status: string; route: string; provider: string | null; attempt_count?: number; latency_ms: number | null; text_preview?: string }[];
  onOpen: (id: number) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>状态</th>
            <th>下游接口</th>
            <th>上游路由</th>
            <th>尝试</th>
            <th>耗时</th>
            <th>文本</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td className="mono">{log.created_at}</td>
              <td>
                <span className="mono" style={{ color: log.status === "success" ? "var(--green)" : "var(--red)" }}>
                  {log.status === "success" ? "成功" : "失败"}
                </span>
              </td>
              <td className="mono">{log.route}</td>
              <td>{log.provider ?? <span className="muted">—</span>}</td>
              <td className="mono">{log.attempt_count ?? "—"}</td>
              <td className="mono">{log.latency_ms != null ? `${log.latency_ms} ms` : "—"}</td>
              <td className="muted" style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {log.text_preview ?? ""}
              </td>
              <td>
                <button type="button" className="button small" onClick={() => onOpen(log.id)}>
                  查看
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function LogsPage() {
  const [limit, setLimit] = useState(50);
  const { data: logs, loading, reload } = useAsync(() => listLogs(limit), [limit]);
  const [detail, setDetail] = useState<RequestLogDetail | null>(null);
  const [open, setOpen] = useState(false);

  const openLog = async (id: number) => {
    try {
      setDetail(await getLog(id));
      setOpen(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <>
      <section className="panel">
        <div className="panel-heading">
          <div className="heading-icon green">≡</div>
          <div>
            <h2>请求日志</h2>
            <p>记录下游请求、上游尝试和上游返回；不保存 API Key</p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <select value={limit} onChange={(event) => setLimit(Number(event.target.value))} style={{ width: "auto" }}>
              <option value={50}>最近 50 条</option>
              <option value={100}>最近 100 条</option>
            </select>
            <button type="button" className="button" onClick={() => void reload()}>
              刷新日志
            </button>
          </div>
        </div>
        {logs && logs.length > 0 ? (
          <LogTable logs={logs} onOpen={(id) => void openLog(id)} />
        ) : (
          <div className="empty-state">{loading ? "加载中…" : "暂无请求日志。通过「翻译测试」或下游接口发起请求后，将在此处显示。"}</div>
        )}
      </section>

      <Modal open={open} onClose={() => setOpen(false)} eyebrow="REQUEST TRACE" title="请求详情" wide>
        <p className="muted" style={{ marginBottom: 12, fontSize: 13 }}>
          下游请求、每次上游请求与上游返回均按时间顺序保存；鉴权信息不会记录。
        </p>
        <pre className="trace">{detail ? JSON.stringify(detail, null, 2) : ""}</pre>
      </Modal>
    </>
  );
}
