import { useState, useEffect, useRef } from "react";
import { getScan } from "../lib/api.js";

const POLL_INTERVAL = 2000;
const TERMINAL_STATUSES = ["completed", "error", "cancelled"];

export function useScanJob(scanId) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!scanId) return;

    async function poll() {
      try {
        const result = await getScan(scanId);
        setData(result);
        if (!TERMINAL_STATUSES.includes(result.status)) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL);
        }
      } catch (err) {
        setError(err?.response?.data?.detail || err.message || "Failed to fetch scan");
      }
    }

    poll();
    return () => clearTimeout(timerRef.current);
  }, [scanId]);

  return { data, error };
}
