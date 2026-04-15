import { useState, useEffect } from "react";
import {
  getApiKey, setApiKey, setUser,
  checkSetupRequired, setupAdmin, login,
} from "../../lib/api.js";

function Logo() {
  return (
    <div className="mb-6 text-center">
      <div
        className="inline-flex w-10 h-10 rounded-lg items-center justify-center text-sm font-bold mb-4"
        style={{ background: "var(--accent)", color: "var(--accent-text)" }}
      >
        P
      </div>
      <h1 className="text-xl font-bold" style={{ fontFamily: "Syne, sans-serif", color: "var(--text-primary)" }}>
        PantauInd
      </h1>
    </div>
  );
}

export default function AuthGate({ children }) {
  const [apiKey, setApiKeyState] = useState(() => getApiKey());
  const [mode, setMode]         = useState(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm]   = useState("");
  const [error, setError]       = useState(null);
  const [loading, setLoading]   = useState(false);

  if (apiKey) return children;

  useEffect(() => {
    checkSetupRequired()
      .then((needed) => setMode(needed ? "setup" : "login"))
      .catch(() => setMode("login"));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      let result;
      if (mode === "setup") {
        if (password !== confirm) {
          setError("Passwords do not match.");
          return;
        }
        result = await setupAdmin(username, password);
      } else {
        result = await login(username, password);
      }
      setApiKey(result.api_key);
      setUser({ username: result.username, role: result.role });
      setApiKeyState(result.api_key);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 503) {
        setMode("setup");
        setError(null);
        return;
      }
      setError(detail || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  if (!mode) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Connecting…</p>
      </div>
    );
  }

  const isSetup = mode === "setup";

  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: "var(--bg-base)" }}>
      <div
        className="w-full max-w-sm rounded-xl p-8"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        <Logo />

        {isSetup && (
          <p className="text-xs text-center mb-5" style={{ color: "var(--accent)" }}>
            First-time setup - create your admin account
          </p>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="text"
            value={username}
            onChange={(e) => { setUsername(e.target.value); setError(null); }}
            placeholder="Username"
            autoFocus
            autoComplete="username"
            className="w-full px-3 py-2.5 rounded text-sm outline-none"
            style={{
              background: "var(--bg-base)",
              border: `1px solid ${error ? "var(--sev-critical-text)" : "var(--border)"}`,
              color: "var(--text-primary)",
            }}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(null); }}
            placeholder="Password"
            autoComplete={isSetup ? "new-password" : "current-password"}
            className="w-full px-3 py-2.5 rounded text-sm outline-none"
            style={{
              background: "var(--bg-base)",
              border: `1px solid ${error ? "var(--sev-critical-text)" : "var(--border)"}`,
              color: "var(--text-primary)",
            }}
          />
          {isSetup && (
            <input
              type="password"
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setError(null); }}
              placeholder="Confirm password"
              autoComplete="new-password"
              className="w-full px-3 py-2.5 rounded text-sm outline-none"
              style={{
                background: "var(--bg-base)",
                border: `1px solid ${error ? "var(--sev-critical-text)" : "var(--border)"}`,
                color: "var(--text-primary)",
              }}
            />
          )}

          {error && <p className="text-xs" style={{ color: "var(--sev-critical-text)" }}>{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded text-sm font-semibold"
            style={{ background: "var(--accent)", color: "var(--accent-text)", opacity: loading ? 0.6 : 1 }}
          >
            {loading ? "…" : isSetup ? "Create Admin Account" : "Sign In"}
          </button>
        </form>

        <p className="text-xs text-center mt-4" style={{ color: "var(--text-muted)" }}>
          {isSetup ? "This account will have admin privileges." : "PantauInd Security Scanner"}
        </p>
      </div>
    </div>
  );
}
