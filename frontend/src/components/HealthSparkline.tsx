import type { HealthEvent } from "../api/types";

export default function HealthSparkline({ history, latest }: { history: HealthEvent[]; latest: string }) {
  const bars = [...history].reverse();
  const padded: (HealthEvent | null)[] = [...Array(Math.max(0, 12 - bars.length)).fill(null), ...bars.slice(-12)];
  const label = latest === "healthy" ? "可用" : latest === "unhealthy" ? "不可用" : "未知";
  return (
    <span className="health-bars" title={`最近 ${bars.length} 次检测 · 当前${label}`}>
      {padded.map((event, index) => (
        <i key={index} className={event ? event.status : ""} />
      ))}
    </span>
  );
}
