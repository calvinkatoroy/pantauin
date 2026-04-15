import { useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import anime from "animejs";
import { getUser, clearApiKey } from "../../lib/api.js";

/* ── Nav icon components (14x14, stroke-based) ───────────────────── */
function NavIcon({ to, active }) {
  const color = active ? "var(--accent)" : "var(--text-muted)";
  const p = {
    width: "14", height: "14", viewBox: "0 0 24 24",
    fill: "none", stroke: color,
    strokeWidth: "1.75", strokeLinecap: "round", strokeLinejoin: "round",
    style: { flexShrink: 0, transition: `stroke var(--duration-fast) var(--transition-fade)` },
  };
  switch (to) {
    case "/history":
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="9" />
          <polyline points="12 7 12 12 15 15" />
        </svg>
      );
    case "/schedules":
      return (
        <svg {...p}>
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      );
    case "/dashboard":
      return (
        <svg {...p}>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
        </svg>
      );
    case "/keywords":
      return (
        <svg {...p}>
          <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z" />
          <line x1="7" y1="7" x2="7.01" y2="7" />
        </svg>
      );
    case "/audit":
      return (
        <svg {...p}>
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      );
    case "/users":
      return (
        <svg {...p}>
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 00-3-3.87" />
          <path d="M16 3.13a4 4 0 010 7.75" />
        </svg>
      );
    default:
      return <span style={{ width: "14px", height: "14px", flexShrink: 0 }} />;
  }
}

const NAV_SECTIONS = [
  {
    label: "Scanner",
    links: [
      { to: "/history",   label: "History" },
      { to: "/schedules", label: "Schedules", roles: ["admin", "analyst"] },
    ],
  },
  {
    label: "Intelligence",
    links: [
      { to: "/dashboard", label: "Overview" },
      { to: "/keywords",  label: "Keywords" },
    ],
  },
  {
    label: "Admin",
    links: [
      { to: "/audit", label: "Audit Log", roles: ["admin", "analyst"] },
      { to: "/users", label: "Users",     roles: ["admin"] },
    ],
  },
];

export default function NavBar({ theme, onToggleTheme }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const user = getUser();
  const role = user?.role || "admin";
  const navRef = useRef(null);

  /* Neon-flicker on active item text whenever route changes */
  useEffect(() => {
    if (!navRef.current) return;
    const indicator = navRef.current.querySelector(".nav-flicker");
    if (!indicator) return;
    anime({
      targets: indicator,
      opacity: [0.15, 1, 0.45, 1, 0.72, 1],
      duration: 320,
      easing: "steps(6)",
    });
  }, [pathname]);

  function isActive(to) {
    return pathname === to || (to !== "/" && pathname.startsWith(to));
  }

  function canSee(link) {
    return !link.roles || link.roles.includes(role);
  }

  function handleLogout() {
    clearApiKey();
    window.location.reload();
  }

  return (
    <aside
      ref={navRef}
      style={{
        width: "220px",
        minHeight: "100vh",
        height: "100vh",
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border)",
        position: "sticky",
        top: 0,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* ── Brand - with radial glow behind it ──────────────────── */}
      <div
        style={{
          padding: "18px 16px 14px",
          background:
            "radial-gradient(ellipse 200% 160% at 50% -10%, rgba(229,77,46,0.13) 0%, transparent 65%)",
        }}
      >
        <Link to="/" style={{ textDecoration: "none", display: "block" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
            <span
              style={{
                fontFamily: "JetBrains Mono, monospace",
                fontWeight: 700,
                fontSize: "13px",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--text-primary)",
              }}
            >
              Pantau
            </span>
            <span
              style={{
                width: "4px",
                height: "4px",
                borderRadius: "50%",
                background: "var(--accent)",
                flexShrink: 0,
                marginBottom: "1px",
              }}
            />
            <span
              style={{
                fontFamily: "JetBrains Mono, monospace",
                fontWeight: 700,
                fontSize: "13px",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--accent)",
              }}
            >
              Ind
            </span>
          </div>
          <div
            style={{
              fontFamily: "JetBrains Mono, monospace",
              fontSize: "10px",
              color: "var(--text-muted)",
              marginTop: "3px",
              letterSpacing: "0.04em",
            }}
          >
            .go.id · .ac.id
          </div>
        </Link>
      </div>

      {/* ── New Scan CTA ────────────────────────────────────────────── */}
      <div style={{ padding: "0 12px 14px" }}>
        <button
          onClick={() => navigate("/")}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "7px",
            width: "100%",
            padding: "8px 12px",
            background: "var(--accent)",
            color: "var(--accent-text)",
            border: "none",
            borderRadius: "var(--radius-md)",
            fontSize: "13px",
            fontWeight: 600,
            letterSpacing: "0.01em",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
        >
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <line x1="7" y1="1" x2="7" y2="13"/>
            <line x1="1" y1="7" x2="13" y2="7"/>
          </svg>
          New Scan
        </button>
      </div>

      {/* ── Divider ─────────────────────────────────────────────────── */}
      <div style={{ height: "1px", background: "var(--border)", margin: "0 0 6px" }} />

      {/* ── Nav Sections ────────────────────────────────────────────── */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
        {NAV_SECTIONS.map((section) => {
          const visibleLinks = section.links.filter(canSee);
          if (visibleLinks.length === 0) return null;
          return (
            <div key={section.label} style={{ marginBottom: "4px" }}>
              <div
                style={{
                  padding: "8px 16px 3px",
                  fontSize: "10px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.10em",
                  color: "var(--text-muted)",
                }}
              >
                {section.label}
              </div>
              {visibleLinks.map((link) => {
                const active = isActive(link.to);
                return (
                  <Link
                    key={link.to}
                    to={link.to}
                    className={active ? "nav-active-item" : ""}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "6px 16px",
                      fontSize: "13px",
                      textDecoration: "none",
                      color: active ? "var(--text-primary)" : "var(--text-secondary)",
                      background: active ? "var(--accent-dim)" : "transparent",
                      borderLeft: active
                        ? "2px solid var(--accent)"
                        : "2px solid transparent",
                      fontWeight: active ? 600 : 400,
                    }}
                    onMouseEnter={(e) => {
                      if (!active) {
                        e.currentTarget.style.color = "var(--text-primary)";
                        e.currentTarget.style.background = "var(--bg-raised)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        e.currentTarget.style.color = "var(--text-secondary)";
                        e.currentTarget.style.background = "transparent";
                      }
                    }}
                  >
                    <NavIcon to={link.to} active={active} />
                    {active ? (
                      <span className="nav-flicker">{link.label}</span>
                    ) : (
                      <span>{link.label}</span>
                    )}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* ── Bottom Utilities ─────────────────────────────────────────── */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "10px 16px 14px",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
        }}
      >
        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "7px",
            width: "100%",
            padding: "5px 0",
            fontSize: "12px",
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
            textAlign: "left",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
        >
          {theme === "dark" ? (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/>
              <line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          )}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>

        {/* User info */}
        {user && (
          <div style={{ padding: "5px 0 4px" }}>
            <div
              style={{
                fontFamily: "JetBrains Mono, monospace",
                fontSize: "12px",
                color: "var(--text-secondary)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {user.username}
            </div>
            <div
              style={{
                fontSize: "10px",
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: user.role === "admin" ? "var(--accent)" : "var(--text-muted)",
                marginTop: "1px",
              }}
            >
              {user.role}
            </div>
          </div>
        )}

        {/* Sign out */}
        <button
          onClick={handleLogout}
          style={{
            display: "block",
            width: "100%",
            padding: "4px 0",
            fontSize: "12px",
            textAlign: "left",
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--sev-critical-text)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
