/**
 * TrendChart - SVG bar chart showing finding counts over multiple scans.
 * No external chart libraries - pure SVG + Tailwind.
 */
import { Link } from "react-router-dom";

const WIDTH = 600;
const HEIGHT = 160;
const BAR_GAP = 6;
const LABEL_HEIGHT = 28;
const CHART_H = HEIGHT - LABEL_HEIGHT;

function formatShortDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("id-ID", {
    month: "short",
    day: "numeric",
    timeZone: "Asia/Jakarta",
  });
}

export default function TrendChart({ domain, points }) {
  if (!points || points.length === 0) {
    return (
      <p className="text-sm" style={{ color: "#4b5563" }}>
        No trend data - only one scan completed for this domain.
      </p>
    );
  }

  const maxTotal = Math.max(...points.map((p) => p.finding_counts.total), 1);
  const barW = Math.max(
    12,
    Math.floor((WIDTH - BAR_GAP * (points.length + 1)) / points.length)
  );

  return (
    <div
      className="rounded-lg p-4 mb-6"
      style={{ background: "#111318", border: "1px solid #2a2d35" }}
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold" style={{ color: "#6b7280" }}>
          TREND -{" "}
          <span className="font-mono" style={{ color: "#e2e8f0" }}>
            {domain}
          </span>
          <span style={{ color: "#4b5563" }}> ({points.length} scans)</span>
        </p>
        <div className="flex gap-3 text-xs" style={{ color: "#4b5563" }}>
          <span><span style={{ color: "#ef4444" }}>■</span> Critical</span>
          <span><span style={{ color: "#f97316" }}>■</span> High</span>
          <span><span style={{ color: "#eab308" }}>■</span> Med</span>
          <span><span style={{ color: "#3b82f6" }}>■</span> Low</span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", height: "auto", overflow: "visible" }}
      >
        {points.map((pt, i) => {
          const fc = pt.finding_counts;
          const total = fc.total || 0;
          const barH = total === 0 ? 2 : Math.max(4, (total / maxTotal) * CHART_H);
          const x = BAR_GAP + i * (barW + BAR_GAP);
          const y = CHART_H - barH;

          // Stacked segments
          const segments = [
            { count: fc.low,      color: "#3b82f6" },
            { count: fc.medium,   color: "#eab308" },
            { count: fc.high,     color: "#f97316" },
            { count: fc.critical, color: "#ef4444" },
          ];

          let stackY = CHART_H;
          const rects = segments.map(({ count, color }) => {
            if (!count) return null;
            const h = Math.max(2, (count / maxTotal) * CHART_H);
            stackY -= h;
            return (
              <rect
                key={color}
                x={x}
                y={stackY}
                width={barW}
                height={h}
                fill={color}
                opacity={0.85}
                rx={2}
              />
            );
          });

          return (
            <g key={pt.scan_id}>
              {/* Background bar */}
              <rect
                x={x}
                y={0}
                width={barW}
                height={CHART_H}
                fill="#1a1d24"
                rx={2}
              />
              {total === 0 && (
                <rect x={x} y={CHART_H - 2} width={barW} height={2} fill="#2a2d35" rx={1} />
              )}
              {rects}
              {/* Date label */}
              <text
                x={x + barW / 2}
                y={HEIGHT - 6}
                textAnchor="middle"
                fontSize={9}
                fill="#4b5563"
              >
                {formatShortDate(pt.created_at)}
              </text>
              {/* Total label on top */}
              {total > 0 && (
                <text
                  x={x + barW / 2}
                  y={Math.max(10, CHART_H - barH - 3)}
                  textAnchor="middle"
                  fontSize={9}
                  fill="#9ca3af"
                >
                  {total}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
