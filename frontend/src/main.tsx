import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import AppShell from "./layout/AppShell";
import DashboardPage from "./pages/dashboard/DashboardPage";
import ProvidersPage from "./pages/providers/ProvidersPage";
import LogsPage from "./pages/logs/LogsPage";
import SettingsPage from "./pages/settings/SettingsPage";
import PlaygroundPage from "./pages/playground/PlaygroundPage";
import "./styles/base.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "providers", element: <ProvidersPage /> },
      { path: "logs", element: <LogsPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "playground", element: <PlaygroundPage /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
