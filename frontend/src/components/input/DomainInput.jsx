import { useState } from "react";

export default function DomainInput({ onSubmit, loading, error }) {
  const [domain, setDomain] = useState("");
  const [focused, setFocused] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = domain.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  }

  const isSweep = domain.startsWith(".");
  const canSubmit = !loading && !!domain.trim();

  return (
    <form onSubmit={handleSubmit}>
      <div
        style={{
          display: "flex",
          gap: "8px",
          alignItems: "center",
        }}
      >
        <div style={{ flex: 1, position: "relative" }}>
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="bkn.go.id  or  .go.id"
            disabled={loading}
            autoComplete="off"
            spellCheck="false"
            style={{
              width: "100%",
              padding: "8px 12px",
              fontFamily: "JetBrains Mono, monospace",
              fontSize: "13px",
              background: "var(--bg-surface)",
              border: `1px solid ${focused ? "var(--accent)" : "var(--border)"}`,
              borderRadius: "6px",
              color: "var(--text-primary)",
              outline: "none",
              caretColor: "var(--accent)",
              transition: "border-color 0.15s",
            }}
          />
          {isSweep && (
            <span
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                fontSize: "10px",
                fontFamily: "JetBrains Mono, monospace",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                padding: "2px 6px",
                borderRadius: "3px",
                background: "var(--sev-low-bg)",
                color: "var(--sev-low-text)",
                pointerEvents: "none",
              }}
            >
              TLD Sweep
            </span>
          )}
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          style={{
            padding: "8px 16px",
            fontSize: "13px",
            fontWeight: 500,
            borderRadius: "6px",
            border: "1px solid var(--border)",
            background: canSubmit ? "var(--accent)" : "var(--bg-raised)",
            color: canSubmit ? "var(--accent-text)" : "var(--text-muted)",
            cursor: canSubmit ? "pointer" : "not-allowed",
            whiteSpace: "nowrap",
            flexShrink: 0,
            transition: "background 0.1s, color 0.1s",
          }}
        >
          {loading ? "Scanning…" : "Scan"}
        </button>
      </div>

      {error && (
        <p
          style={{
            marginTop: "8px",
            fontSize: "12px",
            color: "var(--sev-critical-text)",
          }}
        >
          {error}
        </p>
      )}
    </form>
  );
}
