import type { Provider, UpstreamKindMeta } from "../api/types";

export function formatNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 10_000) return `${Math.round(value / 10_000)}万`;
  return String(value);
}

export default function QuotaBadge({
  provider,
  meta,
  onQuery,
  querying,
}: {
  provider: Provider;
  meta?: UpstreamKindMeta;
  onQuery: (id: number) => void;
  querying: boolean;
}) {
  if (!meta || meta.quota_type === null) {
    return <span className="muted mono">不支持</span>;
  }
  const quota = provider.quota;
  const queryButton = (
    <button type="button" className="button small" disabled={querying} onClick={() => onQuery(provider.id)}>
      {querying ? "查询中…" : quota ? "刷新" : "查询"}
    </button>
  );
  if (!quota) {
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        {queryButton}
        {provider.quota_error && (
          <span className="muted mono" title={provider.quota_error}>
            失败
          </span>
        )}
      </span>
    );
  }
  let display: React.ReactNode;
  if (quota.type === "characters") {
    const used = quota.used ?? 0;
    const limit = quota.limit ?? 0;
    const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
    display = (
      <span className="quota-badge">
        <b>{percent}%</b>
        <span>
          {formatNumber(used)} / {formatNumber(limit)}
        </span>
      </span>
    );
  } else {
    display = (
      <span className="quota-badge">
        <b>
          {quota.currency === "CNY" ? "¥" : (quota.currency ?? "")} {quota.amount?.toFixed(2) ?? "—"}
        </b>
        {provider.quota_limit != null && <span>阈值 ¥{provider.quota_limit}</span>}
      </span>
    );
  }
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      {display}
      {provider.quota_exceeded && <span className="quota-exceeded-tag">已限额跳过</span>}
      {queryButton}
    </span>
  );
}
