import { Link } from "react-router-dom";
import { getDashboard, listProviders } from "../../api/endpoints";
import StatCard from "../../components/StatCard";
import { useAsync } from "../../hooks/useAsync";

function statusLabel(status: string) {
  if (status === "healthy") return "可用";
  if (status === "unhealthy") return "不可用";
  return "未检测";
}

export default function DashboardPage() {
  const stats = useAsync(getDashboard);
  const providers = useAsync(listProviders);
  const summary = stats.data;
  const recentProviders = (providers.data ?? []).slice(0, 6);

  return (
    <>
      <section className="stats-grid" aria-label="服务概览">
        <StatCard label="路由总数" value={summary?.providers.total ?? "—"} hint={`${summary?.providers.enabled ?? 0} 个已启用`} />
        <StatCard label="可用路由" value={summary?.providers.healthy ?? "—"} hint="最近一次健康检测" />
        <StatCard label="24 小时请求" value={summary?.requests.last_24h ?? "—"} hint={`${summary?.requests.success_24h ?? 0} 次成功`} />
        <StatCard label="平均耗时" value={summary?.requests.avg_latency_24h != null ? `${summary.requests.avg_latency_24h} ms` : "—"} hint={`${summary?.providers.quota_exceeded ?? 0} 个路由达到额度阈值`} />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div className="heading-icon green">◎</div>
          <div><h2>路由状态</h2><p>查看已配置上游的运行状态、优先级和最近响应时间。</p></div>
          <Link className="button yellow" to="/providers">管理路由</Link>
        </div>
        {recentProviders.length ? (
          <div className="table-wrap"><table><thead><tr><th>名称</th><th>状态</th><th>优先级</th><th>最近耗时</th></tr></thead><tbody>
            {recentProviders.map((provider) => <tr key={provider.id}>
              <td><strong>{provider.name}</strong><div className="muted mono">{provider.endpoint}</div></td>
              <td><span className={`status-chip ${provider.last_status === "unhealthy" ? "bad" : ""}`}><i />{statusLabel(provider.last_status)}</span></td>
              <td className="mono">{provider.priority} / 权重 {provider.weight}</td>
              <td className="mono">{provider.last_latency_ms != null ? `${provider.last_latency_ms} ms` : "—"}</td>
            </tr>)}
          </tbody></table></div>
        ) : <div className="empty-state">{providers.loading ? "正在加载路由…" : "还没有上游路由。添加一个 DeepL、DeepLX 或其他兼容服务后即可开始翻译。"}</div>}
      </section>

      <section className="panel callout-panel">
        <div><span className="eyebrow">QUICK START</span><h2>下一步：配置路由并验证翻译</h2><p>添加上游服务后，可在“翻译测试”中发送一次真实请求，并在请求日志中查看完整追踪。</p></div>
        <div className="button-row"><Link className="button yellow" to="/providers">添加路由</Link><Link className="button" to="/playground">翻译测试</Link></div>
      </section>
    </>
  );
}
