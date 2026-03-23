import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startScan } from "../lib/api.js";

export function useScan() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function submitScan(domain) {
    setLoading(true);
    setError(null);
    try {
      const { scan_id } = await startScan(domain);
      navigate(`/scan/${scan_id}`);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Failed to start scan");
    } finally {
      setLoading(false);
    }
  }

  return { submitScan, loading, error };
}
