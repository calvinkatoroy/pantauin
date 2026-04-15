import axios from "axios";

const STORAGE_KEY = "pantauind_api_key";
const USER_KEY    = "pantauind_user";   // {username, role}

export function getApiKey() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

export function setApiKey(key) {
  localStorage.setItem(STORAGE_KEY, key);
}

export function clearApiKey() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

// Auth endpoints (no X-API-Key needed)
export async function checkSetupRequired() {
  const { data } = await client.get("/auth/setup-required");
  return data.setup_required;
}

export async function setupAdmin(username, password) {
  const { data } = await client.post("/auth/setup", { username, password });
  return data; // {api_key, username, role}
}

export async function login(username, password) {
  const { data } = await client.post("/auth/login", { username, password });
  return data; // {api_key, username, role}
}

export async function getMe() {
  const { data } = await client.get("/auth/me");
  return data;
}

export async function getUsers() {
  const { data } = await client.get("/auth/users");
  return data;
}

export async function createUser(username, password, role) {
  const { data } = await client.post("/auth/users", { username, password, role });
  return data;
}

export async function updateUser(id, patch) {
  const { data } = await client.patch(`/auth/users/${id}`, patch);
  return data;
}

export async function deleteUser(id) {
  await client.delete(`/auth/users/${id}`);
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  headers: { "Content-Type": "application/json" },
});

// Attach API key header to every request
client.interceptors.request.use((config) => {
  const key = getApiKey();
  if (key) config.headers["X-API-Key"] = key;
  return config;
});

// On 401, clear stored key so AuthGate re-shows
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      clearApiKey();
      window.location.reload();
    }
    return Promise.reject(err);
  }
);

export async function getTrend(domain) {
  const { data } = await client.get("/trend", { params: { domain } });
  return data;
}

export async function bulkScan(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/scan/bulk", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function startScan(domain) {
  const { data } = await client.post("/scan", { domain });
  return data;
}

export async function cancelScan(scanId) {
  const { data } = await client.delete(`/scan/${scanId}`);
  return data;
}

export async function getScan(scanId) {
  const { data } = await client.get(`/scan/${scanId}`);
  return data;
}

export async function getReportUrl(scanId) {
  return `/api/scan/${scanId}/report`;
}

export async function getKeywords(status = null) {
  const params = status ? { status } : {};
  const { data } = await client.get("/keywords", { params });
  return data;
}

export async function getKeywordStats() {
  const { data } = await client.get("/keywords/stats");
  return data;
}

export async function approveKeyword(id) {
  const { data } = await client.patch(`/keywords/${id}/approve`);
  return data;
}

export async function rejectKeyword(id) {
  const { data } = await client.patch(`/keywords/${id}/reject`);
  return data;
}

export async function patchFindingLifecycle(findingId, lifecycleStatus) {
  const { data } = await client.patch(`/finding/${findingId}/lifecycle`, {
    lifecycle_status: lifecycleStatus,
  });
  return data;
}

export async function getSchedules(page = 1, limit = 50) {
  const { data } = await client.get("/schedules", { params: { page, limit } });
  return data;
}

export async function createSchedule(domain, interval) {
  const { data } = await client.post("/schedules", { domain, interval });
  return data;
}

export async function updateSchedule(id, patch) {
  const { data } = await client.patch(`/schedules/${id}`, patch);
  return data;
}

export async function deleteSchedule(id) {
  await client.delete(`/schedules/${id}`);
}

export async function getAuditLog({ page = 1, limit = 50, action = null, actor = null } = {}) {
  const params = { page, limit };
  if (action) params.action = action;
  if (actor) params.actor = actor;
  const { data } = await client.get("/audit", { params });
  return data;
}

export async function getDashboard() {
  const { data } = await client.get("/dashboard");
  return data;
}
