const MODULE_LABELS = {
  dork_sweep:     "Google Dork Sweep",
  page_crawl:     "Page Crawl (Playwright)",
  header_probe:   "Header Analysis",
  path_probe:     "Path Probe",
  cms_detect:     "CMS Fingerprint",
  shodan_probe:   "Shodan Probe",
  subdomain_enum: "Subdomain Enumeration",
};

const STATUS_CONFIG = {
  pending: { color: "var(--text-muted)",          dotClass: "bg-gray-600",                      label: "Pending" },
  running: { color: "var(--sev-medium-text)",      dotClass: "bg-yellow-400 animate-pulse",      label: "Running" },
  done:    { color: "var(--accent-info)",          dotClass: "bg-blue-400",                      label: "Done" },
  error:   { color: "var(--sev-critical-text)",    dotClass: "bg-red-500",                       label: "Error" },
};

export default function ScanProgress({ modules, status }) {
  if (!modules || modules.length === 0) return null;

  return (
    <div
      className="rounded-lg p-4 mb-6"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
          Scan Pipeline
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {modules.map((mod) => {
          const cfg = STATUS_CONFIG[mod.status] || STATUS_CONFIG.pending;
          return (
            <div key={mod.module} className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dotClass}`} />
              <span className="text-sm flex-1" style={{ color: cfg.color }}>
                {MODULE_LABELS[mod.module] || mod.module}
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {cfg.label}
              </span>
              {mod.error && (
                <span className="text-xs" style={{ color: "var(--sev-critical-text)" }}>
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
