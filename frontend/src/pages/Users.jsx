import { useState, useEffect, useCallback } from "react";
import { getUsers, createUser, updateUser, deleteUser, getUser } from "../lib/api.js";
import { useAnimeStagger } from "../hooks/useAnimeStagger.js";
import Breadcrumb from "../components/shared/Breadcrumb.jsx";

const ROLES = ["admin", "analyst", "read-only"];

const ROLE_COLOR = {
  admin:       { bg: "var(--accent-dim)",  text: "var(--accent)" },
  analyst:     { bg: "var(--sev-low-bg)", text: "var(--sev-low-text)" },
  "read-only": { bg: "var(--bg-raised)",  text: "var(--text-secondary)" },
};

function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("id-ID", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}

export default function Users() {
  const [data, setData]             = useState(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const currentUser = getUser();

  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole]         = useState("analyst");
  const [createError, setCreateError] = useState(null);
  const [creating, setCreating]       = useState(false);

  const tbodyRef = useAnimeStagger([data]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getUsers());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(e) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      await createUser(newUsername, newPassword, newRole);
      setNewUsername(""); setNewPassword(""); setNewRole("analyst");
      setShowCreate(false);
      await load();
    } catch (err) {
      setCreateError(err?.response?.data?.detail || "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  async function handleRoleChange(user, role) {
    try {
      await updateUser(user.id, { role });
      await load();
    } catch (err) {
      alert(err?.response?.data?.detail || "Failed to update role");
    }
  }

  async function handleToggleActive(user) {
    try {
      await updateUser(user.id, { is_active: !user.is_active });
      await load();
    } catch (err) {
      alert(err?.response?.data?.detail || "Failed to update user");
    }
  }

  async function handleDelete(user) {
    if (!confirm(`Deactivate user "${user.username}"?`)) return;
    try {
      await deleteUser(user.id);
      await load();
    } catch (err) {
      alert(err?.response?.data?.detail || "Failed to deactivate user");
    }
  }

  const inputStyle = {
    background: "var(--bg-base)",
    border: "1px solid var(--border)",
    color: "var(--text-primary)",
  };

  return (
    <main className="max-w-4xl mx-auto px-6 py-10">
      <Breadcrumb />
      {/* Header */}
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold mb-1" style={{ fontFamily: "Syne, sans-serif", color: "var(--accent)" }}>
            User Management
          </h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Manage analyst accounts and role assignments.
          </p>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="text-sm px-4 py-2 rounded font-semibold"
          style={{ background: "var(--accent)", color: "var(--accent-text)" }}
        >
          {showCreate ? "Cancel" : "+ New User"}
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div
          className="rounded-lg p-5 mb-6"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>Create User</h2>
          <form onSubmit={handleCreate} className="flex flex-wrap gap-3 items-end">
            <div className="flex flex-col gap-1">
              <label className="text-xs" style={{ color: "var(--text-muted)" }}>Username</label>
              <input
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="username"
                required
                className="px-3 py-2 rounded text-sm outline-none"
                style={{ ...inputStyle, width: "160px" }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs" style={{ color: "var(--text-muted)" }}>Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="min 8 chars"
                required
                className="px-3 py-2 rounded text-sm outline-none"
                style={{ ...inputStyle, width: "160px" }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs" style={{ color: "var(--text-muted)" }}>Role</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                className="px-3 py-2 rounded text-sm outline-none"
                style={inputStyle}
              >
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2 rounded text-sm font-semibold"
              style={{ background: "var(--accent)", color: "var(--accent-text)", opacity: creating ? 0.6 : 1 }}
            >
              {creating ? "Creating…" : "Create"}
            </button>
            {createError && (
              <p className="text-xs w-full" style={{ color: "var(--sev-critical-text)" }}>{createError}</p>
            )}
          </form>
        </div>
      )}

      {/* User table */}
      {error ? (
        <p className="text-sm" style={{ color: "var(--sev-critical-text)" }}>Error: {error}</p>
      ) : loading ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      ) : (
        <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--bg-raised)", borderBottom: "1px solid var(--border)" }}>
                {["Username", "Role", "Status", "Created", "Last Login", ""].map((h) => (
                  <th
                    key={h}
                    className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody ref={tbodyRef}>
              {(data?.users || []).map((user) => {
                const isSelf = currentUser?.username === user.username;
                const rc = ROLE_COLOR[user.role] || ROLE_COLOR["read-only"];
                return (
                  <tr
                    key={user.id}
                    data-stagger=""
                    style={{
                      borderBottom: "1px solid var(--border-subtle)",
                      opacity: user.is_active ? 1 : 0.4,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                  >
                    <td className="px-4 py-3">
                      <span className="text-sm font-mono" style={{ color: "var(--text-primary)" }}>
                        {user.username}
                        {isSelf && (
                          <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>(you)</span>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {isSelf ? (
                        <span
                          className="text-xs px-2 py-0.5 rounded font-medium"
                          style={{ background: rc.bg, color: rc.text }}
                        >
                          {user.role}
                        </span>
                      ) : (
                        <select
                          value={user.role}
                          onChange={(e) => handleRoleChange(user, e.target.value)}
                          className="text-xs px-2 py-0.5 rounded outline-none"
                          style={{ background: rc.bg, color: rc.text, border: "none" }}
                        >
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-semibold"
                        style={{ color: user.is_active ? "var(--accent-info)" : "var(--text-muted)" }}
                      >
                        {user.is_active ? "active" : "inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>
                      {formatDate(user.created_at)}
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>
                      {formatDate(user.last_login_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!isSelf && user.is_active && (
                        <button
                          onClick={() => handleDelete(user)}
                          className="text-xs px-2 py-1 rounded"
                          style={{ background: "var(--sev-critical-bg)", color: "var(--sev-critical-text)" }}
                        >
                          Deactivate
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
