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
            PantauInd
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

        {/* Bulk CSV upload */}
        <div className="w-full max-w-xl mt-10">
          <div
            className="rounded-lg p-1"
            style={{ border: "1px solid #2a2d35", background: "#111318" }}
          >
            <div className="px-4 pt-3 pb-2">
              <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "#4b5563" }}>
                Bulk Scan - CSV Upload
              </p>

              {/* Drop zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                className="rounded flex flex-col items-center justify-center py-6 cursor-pointer transition-colors"
                style={{
                  border: `1px dashed ${dragOver ? "#e8c547" : "#2a2d35"}`,
                  background: dragOver ? "#1a1d24" : "transparent",
                }}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={handleFileChange}
                />
                {bulkFile ? (
                  <div className="text-center">
                    <p className="text-sm font-mono" style={{ color: "#e2e8f0" }}>
                      {bulkFile.name}
                    </p>
                    <p className="text-xs mt-1" style={{ color: "#4b5563" }}>
                      Click to change file
                    </p>
                  </div>
                ) : (
                  <div className="text-center">
                    <p className="text-sm" style={{ color: "#4b5563" }}>
                      Drop a <span className="font-mono">.csv</span> file here or click to browse
                    </p>
                    <p className="text-xs mt-1" style={{ color: "#374151" }}>
                      One domain per row - header row optional
                    </p>
                  </div>
                )}
              </div>

              {/* Submit */}
              <div className="flex items-center justify-between mt-3">
                {bulkError ? (
                  <p className="text-xs" style={{ color: "#f87171" }}>{bulkError}</p>
                ) : (
                  <span />
                )}
                <button
                  onClick={handleBulkSubmit}
                  disabled={!bulkFile || bulkLoading}
                  className="px-4 py-2 rounded text-sm font-semibold transition-opacity"
                  style={{
                    background: bulkFile && !bulkLoading ? "#e8c547" : "#1f2937",
                    color: bulkFile && !bulkLoading ? "#0a0c0f" : "#4b5563",
                    cursor: bulkFile && !bulkLoading ? "pointer" : "not-allowed",
                  }}
                >
                  {bulkLoading ? "Queuing…" : "Scan All"}
                </button>
              </div>
            </div>
          </div>
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
