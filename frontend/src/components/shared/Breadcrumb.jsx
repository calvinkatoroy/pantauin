import { Link, useLocation } from "react-router-dom";

/* Route path prefix -> display label */
const ROUTE_LABELS = {
  "/scan/":     "Findings",
  "/history":   "History",
  "/schedules": "Schedules",
  "/keywords":  "Keywords",
  "/dashboard": "Dashboard",
  "/audit":     "Audit Log",
  "/users":     "Users",
};

function HomeIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

export default function Breadcrumb() {
  const { pathname } = useLocation();

  let label = null;
  for (const [prefix, l] of Object.entries(ROUTE_LABELS)) {
    const match = prefix.endsWith("/")
      ? pathname.startsWith(prefix)
      : pathname === prefix;
    if (match) { label = l; break; }
  }

  if (!label) return null;

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        marginBottom: "22px",
        fontSize: "12px",
        color: "var(--text-muted)",
      }}
    >
      <Link
        to="/"
        style={{
          display: "flex",
          alignItems: "center",
          color: "var(--text-muted)",
          textDecoration: "none",
          transition: `color var(--duration-fast) var(--transition-fade)`,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
      >
        <HomeIcon />
      </Link>
      <span style={{ color: "var(--border)", fontSize: "15px", lineHeight: 1 }}>›</span>
      <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{label}</span>
    </nav>
  );
}
