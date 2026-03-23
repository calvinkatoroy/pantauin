import { useState } from "react";

export default function DomainInput({ onSubmit, loading, error }) {
  const [domain, setDomain] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = domain.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  }

  const isSweep = domain.startsWith(".");

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="flex gap-3 items-center">
        <div className="flex-1 relative">
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="bkn.go.id or .go.id"
            disabled={loading}
            className="w-full px-4 py-3 rounded-lg text-sm font-mono outline-none transition-colors"
            style={{
              background: "#1a1d24",
              border: "1px solid #2a2d35",
              color: "#e2e8f0",
              caretColor: "#e8c547",
            }}
            onFocus={(e) => (e.target.style.borderColor = "#e8c547")}
            onBlur={(e) => (e.target.style.borderColor = "#2a2d35")}
            autoComplete="off"
            spellCheck="false"
          />
        </div>
        {isSweep && (
          <span
            className="flex-shrink-0 text-xs px-2 py-0.5 rounded font-semibold"
            style={{ background: "#1e3a5f", color: "#93c5fd" }}
          >
            TLD Sweep
          </span>
        )}
        <button
          type="submit"
          disabled={loading || !domain.trim()}
          className="flex-shrink-0 px-6 py-3 rounded-lg text-sm font-semibold transition-opacity"
          style={{
            background: "#e8c547",
            color: "#0a0c0f",
            opacity: loading || !domain.trim() ? 0.5 : 1,
            cursor: loading || !domain.trim() ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Starting…" : "Scan"}
        </button>
      </div>

      {error && (
        <p className="mt-3 text-sm" style={{ color: "#f87171" }}>
          {error}
        </p>
      )}

      <p className="mt-3 text-xs" style={{ color: "#4b5563" }}>
        Enter a .go.id or .ac.id domain, or a TLD like .go.id to sweep the entire namespace.
      </p>
    </form>
  );
}
