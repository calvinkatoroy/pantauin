import DomainInput from "../components/input/DomainInput.jsx";
import { useScan } from "../hooks/useScan.js";

const EXAMPLE_DOMAINS = ["bkn.go.id", "kemenkeu.go.id", "ui.ac.id", "ugm.ac.id"];

export default function Home() {
  const { submitScan, loading, error } = useScan();

  return (
    <main className="flex flex-col" style={{ minHeight: "calc(100vh - 57px)" }}>
      {/* Center section */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-20">
        {/* Brand */}
        <div className="text-center mb-10">
          <h1
            className="text-5xl font-extrabold mb-3"
            style={{
              fontFamily: "Syne, sans-serif",
              color: "#e2e8f0",
              letterSpacing: "-0.02em",
            }}
          >
            Pantauin
          </h1>
          <p className="text-sm" style={{ color: "#6b7280" }}>
            Detects judi online injection and vulnerability surfaces on{" "}
            <span className="font-mono" style={{ color: "#9ca3af" }}>
              .go.id
            </span>{" "}
            and{" "}
            <span className="font-mono" style={{ color: "#9ca3af" }}>
              .ac.id
            </span>{" "}
            domains.
          </p>
        </div>

        {/* Scan input */}
        <div className="w-full max-w-xl">
          <DomainInput onSubmit={submitScan} loading={loading} error={error} />
        </div>

        {/* Example domains */}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {EXAMPLE_DOMAINS.map((domain) => (
            <button
              key={domain}
              onClick={() => !loading && submitScan(domain)}
              disabled={loading}
              className="text-xs font-mono px-3 py-1.5 rounded transition-all"
              style={{
                background: "transparent",
                border: "1px solid #2a2d35",
                color: "#4b5563",
                cursor: loading ? "not-allowed" : "pointer",
              }}
              onMouseEnter={(e) => {
                if (!loading) {
                  e.currentTarget.style.borderColor = "#e8c547";
                  e.currentTarget.style.color = "#e8c547";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "#2a2d35";
                e.currentTarget.style.color = "#4b5563";
              }}
            >
              {domain}
            </button>
          ))}
        </div>
      </div>

      {/* Footer strip */}
      <div
        className="flex justify-center gap-8 px-6 py-4 border-t text-xs"
        style={{ borderColor: "#1a1d24", color: "#374151" }}
      >
        <span>Gambling Injection Detection</span>
        <span>Passive Vulnerability Surface</span>
        <span>SHA256 Evidence Snapshots</span>
      </div>
    </main>
  );
}
