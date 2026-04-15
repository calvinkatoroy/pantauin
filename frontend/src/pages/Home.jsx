import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import DomainInput from "../components/input/DomainInput.jsx";
import { useScan } from "../hooks/useScan.js";
import { bulkScan } from "../lib/api.js";

const EXAMPLE_DOMAINS = [".go.id", ".ac.id", "bkn.go.id", "kemenkeu.go.id"];

export default function Home() {
  const { submitScan, loading, error } = useScan();
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [bulkFile, setBulkFile] = useState(null);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkError, setBulkError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  function handleFileChange(e) {
    const f = e.target.files?.[0];
    if (f) setBulkFile(f);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f && f.name.endsWith(".csv")) setBulkFile(f);
  }

  async function handleBulkSubmit() {
    if (!bulkFile) return;
    setBulkLoading(true);
    setBulkError(null);
    try {
      await bulkScan(bulkFile);
      navigate("/history");
    } catch (err) {
      setBulkError(err?.response?.data?.detail || err.message || "Bulk scan failed");
    } finally {
      setBulkLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: "720px", margin: "0 auto", padding: "40px 24px" }}>
      {/* Page header */}
      <div style={{ marginBottom: "28px" }}>
        <h1
          style={{
            fontSize: "18px",
            fontWeight: 600,
            color: "var(--text-primary)",
            margin: "0 0 6px",
          }}
        >
          Scan a domain
        </h1>
        <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>
          Detects judi online injection and passive vulnerability surfaces on{" "}
          <code style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "12px" }}>.go.id</code>
          {" "}and{" "}
          <code style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "12px" }}>.ac.id</code>
          {" "}domains. Enter a single domain or a TLD sweep.
        </p>
      </div>

      {/* Scan input */}
      <DomainInput onSubmit={submitScan} loading={loading} error={error} />

      {/* Quick examples */}
      <div style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Examples:</span>
        {EXAMPLE_DOMAINS.map((d) => (
          <button
            key={d}
            onClick={() => !loading && submitScan(d)}
            disabled={loading}
            style={{
              padding: "2px 8px",
              fontSize: "11px",
              fontFamily: "JetBrains Mono, monospace",
              background: "none",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              color: "var(--text-secondary)",
              cursor: loading ? "not-allowed" : "pointer",
              transition: "color 0.1s, border-color 0.1s",
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.currentTarget.style.color = "var(--accent)";
                e.currentTarget.style.borderColor = "var(--accent)";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--text-secondary)";
              e.currentTarget.style.borderColor = "var(--border)";
            }}
          >
            {d}
          </button>
        ))}
      </div>

      {/* Divider */}
      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "28px 0" }} />

      {/* Bulk scan */}
      <div>
        <h2
          style={{
            fontSize: "13px",
            fontWeight: 600,
            color: "var(--text-primary)",
            margin: "0 0 4px",
          }}
        >
          Bulk scan — CSV upload
        </h2>
        <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "0 0 12px" }}>
          One domain per row. Header row optional. Max 500 domains per upload.
        </p>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          style={{
            border: `1px dashed ${dragOver ? "var(--accent)" : "var(--border)"}`,
            borderRadius: "6px",
            padding: "20px",
            cursor: "pointer",
            background: dragOver ? "var(--accent-dim)" : "transparent",
            textAlign: "center",
            transition: "border-color 0.15s, background 0.15s",
          }}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
          {bulkFile ? (
            <>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "13px", color: "var(--text-primary)" }}>
                {bulkFile.name}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                Click to change file
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                Drop a <code style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "12px" }}>.csv</code> file here or click to browse
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                One domain per row — header row optional
              </div>
            </>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "10px" }}>
          {bulkError ? (
            <span style={{ fontSize: "12px", color: "var(--sev-critical-text)" }}>{bulkError}</span>
          ) : (
            <span />
          )}
          <button
            onClick={handleBulkSubmit}
            disabled={!bulkFile || bulkLoading}
            style={{
              padding: "6px 14px",
              fontSize: "13px",
              fontWeight: 500,
              borderRadius: "6px",
              border: "1px solid var(--border)",
              background: bulkFile && !bulkLoading ? "var(--accent)" : "var(--bg-raised)",
              color: bulkFile && !bulkLoading ? "var(--accent-text)" : "var(--text-muted)",
              cursor: bulkFile && !bulkLoading ? "pointer" : "not-allowed",
            }}
          >
            {bulkLoading ? "Queuing…" : "Scan all"}
          </button>
        </div>
      </div>

      {/* Capability reference */}
      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "28px 0" }} />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "16px",
          fontSize: "12px",
          color: "var(--text-secondary)",
        }}
      >
        {[
          ["Gambling injection", "Google CSE dorks + Playwright page crawl"],
          ["Vuln surface", "Headers, exposed paths, CMS fingerprint"],
          ["Evidence", "Playwright screenshot + SHA-256 hash"],
          ["Shodan", "Port/CVE enrichment when API key configured"],
          ["Subdomain enum", "crt.sh CT logs + DNS probe"],
          ["Diff/delta", "New vs. recurring vs. resolved between runs"],
        ].map(([label, desc]) => (
          <div key={label}>
            <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{label}</span>
            <span style={{ color: "var(--text-muted)" }}> — {desc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
