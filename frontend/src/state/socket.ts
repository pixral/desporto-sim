import { useStore } from "./store";
import type { StateView } from "../api/types";

/** Live connection to the simulation. Reconnects with backoff; the server pushes full snapshots. */
export function connectSocket(): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry = 500;
  let timer: number | undefined;

  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => {
      retry = 500;
      useStore.getState().setConnected(true);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as { type: string; data: StateView };
        if (msg.type === "state") useStore.getState().setState(msg.data);
      } catch (err) {
        console.error("bad message", err);
      }
    };
    ws.onclose = () => {
      useStore.getState().setConnected(false);
      if (!closed) {
        timer = window.setTimeout(open, retry);
        retry = Math.min(retry * 2, 8000);
      }
    };
    ws.onerror = () => ws?.close();
  };
  open();
  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    ws?.close();
  };
}
