import type { ServerMessage } from "../types";

export const WS_URL = (import.meta as any).env?.VITE_WS_URL ?? "ws://localhost:8000/ws/conversation";

export interface ConversationSocket {
  sendUtterance: (text: string) => void;
  close: () => void;
}

export function connectConversationSocket(
  onMessage: (message: ServerMessage) => void,
  onStatusChange: (status: "connecting" | "open" | "closed") => void
): ConversationSocket {
  const socket = new WebSocket(WS_URL);

  onStatusChange("connecting");

  socket.addEventListener("open", () => onStatusChange("open"));
  socket.addEventListener("close", () => onStatusChange("closed"));
  socket.addEventListener("error", () => onStatusChange("closed"));

  socket.addEventListener("message", (event) => {
    try {
      const parsed = JSON.parse(event.data) as ServerMessage;
      onMessage(parsed);
    } catch {
      // Ignore malformed frames rather than crashing the UI.
    }
  });

  return {
    sendUtterance(text: string) {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "utterance", text }));
      }
    },
    close() {
      socket.close();
    },
  };
}
