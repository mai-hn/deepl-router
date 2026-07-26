import { useEffect, useState } from "react";
import { listUpstreamKinds } from "../api/endpoints";
import type { UpstreamKindMeta } from "../api/types";

let cache: UpstreamKindMeta[] | null = null;
let pending: Promise<UpstreamKindMeta[]> | null = null;

export function fetchUpstreamKinds(): Promise<UpstreamKindMeta[]> {
  if (cache) return Promise.resolve(cache);
  pending ??= listUpstreamKinds().then((kinds) => {
    cache = kinds;
    pending = null;
    return kinds;
  });
  return pending;
}

export function useUpstreamKinds(): UpstreamKindMeta[] {
  const [kinds, setKinds] = useState<UpstreamKindMeta[]>(cache ?? []);
  useEffect(() => {
    if (!cache) void fetchUpstreamKinds().then(setKinds);
  }, []);
  return kinds;
}

export function kindMeta(kinds: UpstreamKindMeta[], kind: string): UpstreamKindMeta | undefined {
  return kinds.find((item) => item.kind === kind);
}
