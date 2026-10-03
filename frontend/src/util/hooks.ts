import { useEffect, useRef, useState } from "react";

/**
 * Fetch data and re-fetch whenever `key` changes (e.g. the simulated day or phase).
 * Keeps showing the previous result while refreshing (no skeleton flash).
 */
export function useLive<T>(fetcher: () => Promise<T>, key: unknown): { data: T | null; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;
  useEffect(() => {
    let alive = true;
    fetchRef
      .current()
      .then((d) => {
        if (alive) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [key, nonce]);
  return { data, error, reload: () => setNonce((n) => n + 1) };
}
