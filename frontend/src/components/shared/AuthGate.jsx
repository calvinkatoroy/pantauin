import { useState } from "react";
import { setApiKey, getApiKey } from "../../lib/api.js";

export default function AuthGate({ children }) {
  const [stored, setStored] = useState(() => getApiKey());
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);

  if (stored) return children;

  function handleSubmit(e) {
    e.preventDefault();
    const key = input.trim();
    if (!key) {
      setError("API key cannot be empty.");
      return;
    }
    setApiKey(key);
    setStored(key);
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{ background: "#0a0c0f" }}
    >
      <div
        className="w-full max-w-sm rounded-xl p-8"
        style={{ background: "#111318", border: "1px solid #2a2d35" }}
      >
        <div className="mb-6 text-center">
          <div
            className="inline-flex w-10 h-10 rounded-lg items-center justify-center text-sm font-bold mb-4"
            style={{ background: "#e8c547", color: "#0a0c0f" }}
          >
            P
          </div>
          <h1
            className="text-xl font-bold"
            style={{ fontFamily: "Syne, sans-serif", color: "#e2e8f0" }}
          >
            PantauInd
          </h1>
          <p className="text-xs mt-1" style={{ color: "#4b5563" }}>
            Enter your API key to continue
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="password"
            value={input}
            onChange={(e) => { setInput(e.target.value); setError(null); }}
            placeholder="API key"
            autoFocus
            className="w-full px-3 py-2.5 rounded text-sm font-mono outline-none"
            style={{
              background: "#0a0c0f",
              border: `1px solid ${error ? "#ef4444" : "#2a2d35"}`,
              color: "#e2e8f0",
            }}
          />
          {error && (
            <p className="text-xs" style={{ color: "#f87171" }}>{error}</p>
          )}
          <button
            type="submit"
            className="w-full py-2.5 rounded text-sm font-semibold transition-opacity"
            style={{ background: "#e8c547", color: "#0a0c0f" }}
          >
            Continue
          </button>
        </form>
      </div>
    </div>
  );
}
