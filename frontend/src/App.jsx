import { Routes, Route } from "react-router-dom";
import NavBar from "./components/shared/NavBar.jsx";
import AuthGate from "./components/shared/AuthGate.jsx";
import Home from "./pages/Home.jsx";
import ScanReport from "./pages/ScanReport.jsx";
import Keywords from "./pages/Keywords.jsx";
import History from "./pages/History.jsx";
import Schedules from "./pages/Schedules.jsx";

export default function App() {
  return (
    <AuthGate>
      <div className="min-h-screen" style={{ background: "#0a0c0f" }}>
        <NavBar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/scan/:scanId" element={<ScanReport />} />
          <Route path="/keywords" element={<Keywords />} />
          <Route path="/history" element={<History />} />
          <Route path="/schedules" element={<Schedules />} />
        </Routes>
      </div>
    </AuthGate>
  );
}
