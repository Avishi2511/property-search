import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  disabled: boolean;
  connectionStatus: "connecting" | "open" | "closed";
  micSupported: boolean;
  listening: boolean;
  partialTranscript: string;
  onToggleMic: () => void;
  aiSpeaking: boolean;
  voiceEnabled: boolean;
  onToggleVoiceEnabled: () => void;
}

export function ConversationPanel({
  messages,
  onSend,
  disabled,
  connectionStatus,
  micSupported,
  listening,
  partialTranscript,
  onToggleMic,
  aiSpeaking,
  voiceEnabled,
  onToggleVoiceEnabled,
}: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, partialTranscript]);

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
        <div className="header-controls">
          {aiSpeaking && <span className="speaking-indicator">🔊 speaking…</span>}
          <label className="voice-toggle">
            <input type="checkbox" checked={voiceEnabled} onChange={onToggleVoiceEnabled} />
            voice reply
          </label>
          <span className={`status-dot status-${connectionStatus}`} title={connectionStatus} />
        </div>
      </header>

      <div className="messages" ref={scrollRef}>
        {messages.length === 0 && (
          <p className="empty-hint">
            Tell me what you're looking for — e.g. "I want a 3BHK in Bangalore around two crore." Type it, or use
            the mic.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message-${m.role}`}>
            <span className="message-badge">{m.role === "buyer" ? "🎙 Buyer" : "🤖 AI"}</span>
            <p>{m.text}</p>
          </div>
        ))}
        {listening && partialTranscript && (
          <div className="message message-buyer message-partial">
            <span className="message-badge">🎙 Buyer (listening…)</span>
            <p>{partialTranscript}</p>
          </div>
        )}
      </div>

      <div className="composer">
        {micSupported && (
          <button
            type="button"
            className={`mic-button ${listening ? "mic-button-active" : ""}`}
            onClick={onToggleMic}
            title={listening ? "Stop listening" : "Start listening"}
          >
            {listening ? "⏹" : "🎙"}
          </button>
        )}
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
      {!micSupported && (
        <p className="mic-unsupported-hint">
          Voice input isn't supported in this browser — try Chrome. You can still type.
        </p>
      )}
    </section>
  );
}
