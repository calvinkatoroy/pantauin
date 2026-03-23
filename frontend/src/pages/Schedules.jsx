import { useState, useEffect, useCallback } from "react";
import { getSchedules, createSchedule, updateSchedule, deleteSchedule } from "../lib/api.js";

const INTERVAL_LABELS = { daily: "Daily", weekly: "Weekly", monthly: "Monthly" };
const INTERVAL_COLORS = {
  daily:   { bg: "#172554", color: "#93c5fd" },
  weekly:  { bg: "#14532d", color: "#86efac" },
  monthly: { bg: "#1c1917", color: "#d6d3d1" },
};

function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("id-ID", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function Schedules() {
  const [schedules, setSchedules] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [domain, setDomain] = useState("");
  const [interval, setInterval] = useState("weekly");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSchedules();
      setSchedules(data.schedules);
      setTotal(data.total);
    } catch (e) {
      setError("Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(e) {
    e.preventDefault();
    if (!domain.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await createSchedule(domain.trim(), interval);
      setDomain("");
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to create schedule");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(schedule) {
    try {
      const updated = await updateSchedule(schedule.id, { enabled: !schedule.enabled });
      setSchedules((prev) => prev.map((s) => s.id === schedule.id ? { ...s, enabled: updated.enabled } : s));
    } catch (_) {}
  }

  async function handleDelete(id) {
    try {
      await deleteSchedule(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      setTotal((n) => n - 1);
    } catch (_) {}
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1" style={{ fontFamily: "Syne, sans-serif", color: "#e2e8f0" }}>
          Scheduled Scans
        </h1>
        <p className="text-sm" style={{ color: "#6b7280" }}>
          Automatically scan a domain on a recurring schedule. Dispatches a full pipeline scan on each run.
        </p>
      </div>

      {/* Create form */}
      <form
        onSubmit={handleCreate}
        className="flex gap-2 flex-wrap mb-8 p-4 rounded-lg"
        style={{ background: "#111318", border: "1px solid #2a2d35" }}
      >
        <input
          type="text"
          placeholder="bkn.go.id or .go.id"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          required
          className="flex-1 rounded px-3 py-2 text-sm outline-none font-mono"
          style={{
            background: "#0a0c0f", color: "#e2e8f0",
            border: "1px solid #2a2d35", minWidth: "200px",
          }}
        />
        <select
          value={interval}
          onChange={(e) => setInterval(e.target.value)}
          className="rounded px-3 py-2 text-sm outline-none"
          style={{ background: "#0a0c0f", color: "#e2e8f0", border: "1px solid #2a2d35" }}
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
        <button
          type="submit"
          disabled={submitting}
          className="px-5 py-2 rounded text-sm font-semibold transition-opacity"
          style={{
            background: "#e8c547", color: "#0a0c0f",
            opacity: submitting ? 0.6 : 1,
          }}
        >
          {submitting ? "Scheduling…" : "Add Schedule"}
        </button>
        {error && (
          <p className="w-full text-xs mt-1" style={{ color: "#f87171" }}>{error}</p>
        )}
      </form>

      {/* Schedule list */}
      {loading ? (
        <p className="text-sm" style={{ color: "#6b7280" }}>Loading…</p>
      ) : schedules.length === 0 ? (
        <div
          className="text-center py-16 rounded-lg"
          style={{ background: "#111318", border: "1px solid #2a2d35" }}
        >
          <p className="text-sm" style={{ color: "#4b5563" }}>No schedules yet. Add one above.</p>
        </div>
      ) : (
        <div className="rounded-lg overflow-hidden" style={{ background: "#111318", border: "1px solid #2a2d35" }}>
          <div className="px-4 py-3 border-b" style={{ borderColor: "#2a2d35" }}>
            <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: "#6b7280" }}>
              {total} schedule{total !== 1 ? "s" : ""}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid #2a2d35" }}>
                {["Domain", "Interval", "Enabled", "Last Run", "Next Run", ""].map((h) => (
                  <th key={h} className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider" style={{ color: "#4b5563" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id} style={{ borderBottom: "1px solid #1a1d24", opacity: s.enabled ? 1 : 0.5 }}>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "#e2e8f0" }}>{s.domain}</td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs px-2 py-0.5 rounded uppercase tracking-wider font-semibold"
                      style={INTERVAL_COLORS[s.interval] || { bg: "#1f2937", color: "#9ca3af" }}
                    >
                      {INTERVAL_LABELS[s.interval] || s.interval}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggle(s)}
                      className="relative inline-flex h-5 w-9 rounded-full transition-colors"
                      style={{ background: s.enabled ? "#e8c547" : "#374151" }}
                      title={s.enabled ? "Disable" : "Enable"}
                    >
                      <span
                        className="inline-block h-4 w-4 rounded-full bg-white transition-transform mt-0.5"
                        style={{ transform: s.enabled ? "translateX(18px)" : "translateX(2px)" }}
                      />
                    </button>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: "#6b7280" }}>{formatDate(s.last_run_at)}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: s.enabled ? "#e2e8f0" : "#4b5563" }}>
                    {formatDate(s.next_run_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="text-xs px-2 py-1 rounded transition-colors"
                      style={{ color: "#6b7280", background: "transparent" }}
                      onMouseEnter={(e) => (e.target.style.color = "#f87171")}
                      onMouseLeave={(e) => (e.target.style.color = "#6b7280")}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
