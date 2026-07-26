import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { request } from "../api/client";
import styles from "./AppShell.module.css";

const NAV = [
  { group: "OVERVIEW", items: [{ to: "/", icon: "◆", label: "仪表盘" }] },
  {
    group: "MANAGE",
    items: [
      { to: "/providers", icon: "↔", label: "供应商" },
      { to: "/settings", icon: "▦", label: "设置" },
    ],
  },
  {
    group: "OBSERVE",
    items: [
      { to: "/logs", icon: "≡", label: "请求日志" },
      { to: "/playground", icon: "文", label: "翻译测试" },
    ],
  },
];

const TITLES: Record<string, { title: string; subtitle: string }> = {
  "/": { title: "仪表盘", subtitle: "通道健康、请求量与余额概览" },
  "/providers": { title: "供应商", subtitle: "管理翻译上游路由、额度与健康状态" },
  "/settings": { title: "设置", subtitle: "路由策略与下游访问凭证" },
  "/logs": { title: "请求日志", subtitle: "下游请求、上游尝试与返回详情" },
  "/playground": { title: "翻译测试", subtitle: "使用当前路由配置发起真实翻译请求" },
};

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "1");
  const [healthy, setHealthy] = useState(true);
  const location = useLocation();
  const page = TITLES[location.pathname] ?? TITLES["/"];

  useEffect(() => {
    localStorage.setItem("sidebar-collapsed", collapsed ? "1" : "0");
  }, [collapsed]);

  useEffect(() => {
    request<{ status: string }>("/api/health")
      .then((body) => setHealthy(body.status === "ok"))
      .catch(() => setHealthy(false));
  }, [location.pathname]);

  return (
    <div className={styles.shell}>
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ""}`}>
        <NavLink to="/" className={styles.brand}>
          <span className={styles.brandMark}>T</span>
          {!collapsed && <span className={styles.brandName}>Translate Router</span>}
        </NavLink>
        <nav className={styles.nav}>
          {NAV.map((section) => (
            <div key={section.group}>
              {!collapsed && <div className={styles.navGroup}>{section.group}</div>}
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ""}`}
                  title={item.label}
                >
                  <span className={styles.navIcon}>{item.icon}</span>
                  {!collapsed && <span>{item.label}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className={styles.sidebarFooter}>
          {!collapsed && <span className={styles.version}>v0.4.0</span>}
          <button
            type="button"
            className={styles.collapseBtn}
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? "展开侧边栏" : "折叠侧边栏"}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
      </aside>
      <div className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topbarTitle}>
            <h1>{page.title}</h1>
            <p>{page.subtitle}</p>
          </div>
          <span className={`status-chip ${healthy ? "" : "bad"}`}>
            <i />
            {healthy ? "服务运行正常" : "服务异常"}
          </span>
        </header>
        <div className={styles.stripe} aria-hidden="true" />
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
