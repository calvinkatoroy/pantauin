/**
 * TrendChart - SVG bar chart showing finding counts over multiple scans.
 * No external chart libraries - pure SVG + Anime.js for bar-grow entry.
 */
import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import anime from "animejs";

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
  const svgRef = useRef(null);

  // Animate bars growing up from baseline when data changes
  useEffect(() => {
    if (!svgRef.current || !points?.length) return;

    const bars = svgRef.current.querySelectorAll(".chart-bar");
    if (!bars.length) return;

    anime({
      targets: bars,
      height: (el) => [0, parseFloat(el.dataset.finalH)],
      y: (el) => [CHART_H, parseFloat(el.dataset.finalY)],
      duration: 480,
      delay: anime.stagger(28, { start: 60 }),
      easing: "cubicBezier(0.16, 1, 0.30, 1)",
    });

    // Fade in totals after bars finish
    const labels = svgRef.current.querySelectorAll(".chart-label");
    if (labels.length) {
      anime({
        targets: labels,
        opacity: [0, 1],
        duration: 200,
        delay: anime.stagger(28, { start: 320 }),
        easing: "linear",
      });
    }
  }, [points]);

  if (!points || points.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
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
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        padding: "16px",
        marginBottom: "24px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <p style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>
          TREND -{" "}
          <span style={{ fontFamily: "JetBrains Mono, monospace", color: "var(--text-primary)", letterSpacing: 0 }}>
            {domain}
          </span>
          <span style={{ color: "var(--text-muted)", fontWeight: 400 }}> ({points.length} scans)</span>
        </p>
        <div style={{ display: "flex", gap: "12px", fontSize: "11px", color: "var(--text-muted)" }}>
          <span><span style={{ color: "var(--sev-critical-text)" }}>■</span> Crit</span>
          <span><span style={{ color: "var(--sev-high-text)" }}>■</span> High</span>
          <span><span style={{ color: "var(--sev-medium-text)" }}>■</span> Med</span>
          <span><span style={{ color: "var(--sev-low-text)" }}>■</span> Low</span>
        </div>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", height: "auto", overflow: "visible" }}
      >
        {points.map((pt, i) => {
          const fc = pt.finding_counts;
          const total = fc.total || 0;
          const barH = total === 0 ? 2 : Math.max(4, (total / maxTotal) * CHART_H);
          const x = BAR_GAP + i * (barW + BAR_GAP);

          const segments = [
            { count: fc.low,      color: "var(--sev-low-text)" },
            { count: fc.medium,   color: "var(--sev-medium-text)" },
            { count: fc.high,     color: "var(--sev-high-text)" },
            { count: fc.critical, color: "var(--sev-critical-text)" },
          ];

          // Compute final stack positions for Anime.js data attributes
          let stackY = CHART_H;
          const segmentData = segments.map(({ count, color }) => {
            if (!count) return null;
            const h = Math.max(2, (count / maxTotal) * CHART_H);
            stackY -= h;
            return { h, y: stackY, color };
          });

          return (
            <g key={pt.scan_id}>
              {/* Background track */}
              <rect
                x={x}
                y={0}
                width={barW}
                height={CHART_H}
                fill="var(--bg-raised)"
                rx={2}
              />

              {total === 0 && (
                <rect
                  x={x}
                  y={CHART_H - 2}
                  width={barW}
                  height={2}
                  fill="var(--border)"
                  rx={1}
                />
              )}

              {/* Stacked bars - start at y=CHART_H height=0, Anime.js animates to finals */}
              {segmentData.map((seg, si) => {
                if (!seg) return null;
                return (
                  <rect
                    key={si}
                    className="chart-bar"
                    x={x}
                    y={CHART_H}        /* initial: at baseline */
                    width={barW}
                    height={0}         /* initial: zero height */
                    fill={seg.color}
                    opacity={0.9}
                    rx={si === segmentData.filter(Boolean).length - 1 ? 2 : 0}
                    data-final-h={seg.h}
                    data-final-y={seg.y}
                  />
                );
              })}

              {/* Date label */}
              <text
                x={x + barW / 2}
                y={HEIGHT - 6}
                textAnchor="middle"
                fontSize={9}
                fill="var(--text-muted)"
              >
                {formatShortDate(pt.created_at)}
              </text>

              {/* Total count - fades in via Anime.js after bars grow */}
              {total > 0 && (
                <text
                  className="chart-label"
                  x={x + barW / 2}
                  y={Math.max(10, CHART_H - barH - 4)}
                  textAnchor="middle"
                  fontSize={9}
                  fill="var(--text-secondary)"
                  opacity={0}  /* starts invisible, Anime.js fades in */
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
