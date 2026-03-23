import { useState } from "react";

export default function EvidenceViewer({ screenshotPath, screenshotHash }) {
  const [expanded, setExpanded] = useState(false);

  if (!screenshotPath) return null;

  const imgUrl = `/evidence/${screenshotPath}`;

  return (
    <div className="mt-3">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-xs transition-colors"
        style={{ color: "#e8c547" }}
      >
        <span>{expanded ? "▼" : "▶"}</span>
        {expanded ? "Hide screenshot" : "View evidence screenshot"}
      </button>

      {expanded && (
        <div className="mt-2">
          <img
            src={imgUrl}
            alt="Evidence screenshot"
            className="rounded border max-w-full"
            style={{ borderColor: "#2a2d35" }}
            loading="lazy"
          />
          {screenshotHash && (
            <p className="mt-1 text-xs font-mono" style={{ color: "#4b5563" }}>
              SHA256: {screenshotHash}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
