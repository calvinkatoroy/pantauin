const MODULE_LABELS = {
  dork_sweep:  "Google Dork Sweep",
  page_crawl:  "Page Crawl (Playwright)",
  header_probe: "Header Analysis",
  path_probe:  "Path Probe",
  cms_detect:  "CMS Fingerprint",
};

const STATUS_CONFIG = {
  pending: { color: "#4b5563", dot: "bg-gray-600", label: "Pending" },
  running: { color: "#e8c547", dot: "bg-yellow-400 animate-pulse", label: "Running" },
  done:    { color: "#22c55e", dot: "bg-green-500", label: "Done" },
  error:   { color: "#ef4444", dot: "bg-red-500", label: "Error" },
};

export default function ScanProgress({ modules, status }) {
  if (!modules || modules.length === 0) return null;

  return (
    <div
      className="rounded-lg p-4 mb-6"
      style={{ background: "#111318", border: "1px solid #2a2d35" }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#4b5563" }}>
          Scan Pipeline
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {modules.map((mod) => {
          const cfg = STATUS_CONFIG[mod.status] || STATUS_CONFIG.pending;
          return (
            <div key={mod.module} className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
              <span className="text-sm flex-1" style={{ color: cfg.color }}>
                {MODULE_LABELS[mod.module] || mod.module}
              </span>
              <span className="text-xs" style={{ color: "#4b5563" }}>
                {cfg.label}
              </span>
              {mod.error && (
                <span className="text-xs" style={{ color: "#f87171" }}>
                  {mod.error}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
