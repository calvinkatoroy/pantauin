import { Link, useLocation } from "react-router-dom";

export default function NavBar() {
  const { pathname } = useLocation();

  const navLinks = [
    { to: "/",         label: "Scanner" },
    { to: "/history",  label: "History" },
    { to: "/keywords", label: "Keywords" },
  ];

  return (
    <nav
      className="flex items-center justify-between px-6 py-4 border-b"
      style={{ background: "#111318", borderColor: "#2a2d35" }}
    >
      <div className="flex items-center gap-6">
        <Link to="/" className="flex items-center gap-3 no-underline">
          <div
            className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold"
            style={{ background: "#e8c547", color: "#0a0c0f" }}
          >
            P
          </div>
          <span
            className="text-base font-bold tracking-wide"
            style={{ fontFamily: "Syne, sans-serif", color: "#e8c547" }}
          >
            Pantauin
          </span>
        </Link>

        <div className="flex gap-1">
          {navLinks.map((link) => {
            const active = pathname === link.to || (link.to !== "/" && pathname.startsWith(link.to));
            return (
              <Link
                key={link.to}
                to={link.to}
                className="px-3 py-1.5 rounded text-sm no-underline transition-colors"
                style={{
                  color: active ? "#e8c547" : "#6b7280",
                  background: active ? "#1a1d24" : "transparent",
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </div>

      <div className="text-xs" style={{ color: "#4b5563" }}>
        .go.id / .ac.id
      </div>
    </nav>
  );
}
