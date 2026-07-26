import type { UpstreamKindMeta } from "../api/types";

export default function KindBadge({ meta, kind }: { meta?: UpstreamKindMeta; kind: string }) {
  return (
    <span className="kind-badge" style={{ "--kind-color": meta?.color ?? "#6e42db" } as React.CSSProperties}>
      {meta?.label ?? kind}
    </span>
  );
}
