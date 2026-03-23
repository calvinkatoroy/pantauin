import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export async function startScan(domain) {
  const { data } = await client.post("/scan", { domain });
  return data; // { scan_id }
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
