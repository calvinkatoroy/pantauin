import { Routes, Route } from "react-router-dom";
import NavBar from "./components/shared/NavBar.jsx";
import AuthGate from "./components/shared/AuthGate.jsx";
import Home from "./pages/Home.jsx";
import ScanReport from "./pages/ScanReport.jsx";
import Keywords from "./pages/Keywords.jsx";
import History from "./pages/History.jsx";
import Schedules from "./pages/Schedules.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import AuditLog from "./pages/AuditLog.jsx";
import Users from "./pages/Users.jsx";
import { useTheme } from "./hooks/useTheme.js";

export default function App() {
  const { theme, toggle } = useTheme();

  return (
    <AuthGate>
      <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-base)" }}>
        <NavBar theme={theme} onToggleTheme={toggle} />
        <main style={{ flex: 1, minWidth: 0, overflow: "auto" }}>
          <Routes>
            <Route path="/"             element={<Home />} />
            <Route path="/scan/:scanId" element={<ScanReport />} />
            <Route path="/keywords"     element={<Keywords />} />
            <Route path="/history"      element={<History />} />
            <Route path="/schedules"    element={<Schedules />} />
            <Route path="/dashboard"    element={<Dashboard />} />
            <Route path="/audit"        element={<AuditLog />} />
            <Route path="/users"        element={<Users />} />
          </Routes>
        </main>
      </div>
    </AuthGate>
  );
}
