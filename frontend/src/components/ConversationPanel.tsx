import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  disabled: boolean;
  connectionStatus: "connecting" | "open" | "closed";
}

export function ConversationPanel({ messages, onSend, disabled, connectionStatus }: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function submit() {
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    setDraft("");
  }

  return (
    <section className="panel conversation-panel">
      <header className="panel-header">
        <h2>Conversation</h2>
        <span className={`status-dot status-${connectionStatus}`} title={connectionStatus} />
      </header>

      <div className="messages" ref={scrollRef}>
        {messages.length === 0 && (
          <p className="empty-hint">
            Tell me what you're looking for — e.g. "I want a 3BHK in Bangalore around two crore."
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message-${m.role}`}>
            <span className="message-badge">{m.role === "buyer" ? "🎙 Buyer" : "🤖 AI"}</span>
            <p>{m.text}</p>
          </div>
        ))}
      </div>

      <div className="composer">
        <input
          type="text"
          value={draft}
          placeholder="Type what you'd tell the agent…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          disabled={disabled}
        />
        <button onClick={submit} disabled={disabled || !draft.trim()}>
          Send
        </button>
      </div>
    </section>
  );
}
