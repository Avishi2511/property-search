import { useEffect, useRef, useState } from "react";
import { BuyerProfilePanel } from "./components/BuyerProfilePanel";
import { ConversationPanel } from "./components/ConversationPanel";
import { NextQuestionExplainer } from "./components/NextQuestionExplainer";
import { SearchSpaceFunnel } from "./components/SearchSpaceFunnel";
import { TopMatchesPanel } from "./components/TopMatchesPanel";
import type { ChatMessage, DiscoveryDecision, Profile, SearchSpace, TopMatch } from "./types";
import type { VoiceProvider } from "./voice/VoiceProvider";
import { WebSpeechProvider } from "./voice/WebSpeechProvider";
import { connectConversationSocket, type ConversationSocket } from "./ws/client";

function App() {
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [searchSpace, setSearchSpace] = useState<SearchSpace | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryDecision | null>(null);
  const [topMatches, setTopMatches] = useState<TopMatch[]>([]);

  const [micSupported, setMicSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  const socketRef = useRef<ConversationSocket | null>(null);
  const voiceRef = useRef<VoiceProvider | null>(null);
  const voiceEnabledRef = useRef(voiceEnabled);
  voiceEnabledRef.current = voiceEnabled;

  useEffect(() => {
    const socket = connectConversationSocket((message) => {
      if (message.type === "init") {
        setProfile(message.profile);
        setSearchSpace(message.search_space);
      } else if (message.type === "turn_update") {
        setProfile(message.profile);
        setSearchSpace(message.search_space);
        setDiscovery(message.discovery);
        setTopMatches(message.top_matches);
        setMessages((prev) => [...prev, { role: "ai", text: message.response_text }]);

        if (voiceEnabledRef.current && voiceRef.current?.isSupported()) {
          setAiSpeaking(true);
          voiceRef.current.speak(message.response_text, () => setAiSpeaking(false));
        }
      }
    }, setStatus);

    socketRef.current = socket;
    return () => socket.close();
  }, []);

  useEffect(() => {
    const voice = new WebSpeechProvider();
    voiceRef.current = voice;
    setMicSupported(voice.isSupported());
    voice.onListeningChange(setListening);
    return () => voice.stopListening();
  }, []);

  function handleSend(text: string) {
    setPartialTranscript("");
    setMessages((prev) => [...prev, { role: "buyer", text }]);
    socketRef.current?.sendUtterance(text);
  }

  function handleToggleMic() {
    const voice = voiceRef.current;
    if (!voice) return;
    if (listening) {
      voice.stopListening();
    } else {
      voice.interrupt(); // manually starting the mic always counts as an interruption
      setAiSpeaking(false);
      voice.startListening(setPartialTranscript, (text) => {
        setPartialTranscript("");
        if (text) handleSend(text);
      });
    }
  }

  const totalListings = searchSpace?.history[0] ?? null;

  return (
    <div className="app-shell">
      <nav className="navbar">
        <div className="navbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
                <path
                  d="M3 11.5 12 4l9 7.5M5.5 10v9a1 1 0 0 0 1 1H10v-5.5h4V20h3.5a1 1 0 0 0 1-1v-9"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span className="brand-name">Basera</span>
          </div>
          <div className="navbar-links">
            <span className="navbar-link navbar-link-active">Talk to Basera</span>
            <span className="navbar-link">How it works</span>
          </div>
          <div className={`connection-pill connection-pill-${status}`}>
            <span className="connection-dot" />
            {status === "open" ? "Assistant online" : status === "connecting" ? "Connecting…" : "Disconnected"}
          </div>
        </div>
      </nav>

      <header className="hero">
        <div className="hero-inner">
          <p className="hero-eyebrow">Bangalore · voice-first property search</p>
          <h1>Tell us what home means to you — we'll ask the rest.</h1>
          <p className="hero-subtitle">
            No filters to fill in. Just talk — about budget, family, commute, whatever matters — and Basera
            figures out which question to ask next to find your match fastest.
          </p>
          <div className="hero-stats">
            <div className="hero-stat">
              <strong>{totalListings ?? "550+"}</strong>
              <span>listings tracked</span>
            </div>
            <div className="hero-stat">
              <strong>18</strong>
              <span>Bangalore localities</span>
            </div>
            <div className="hero-stat">
              <strong>{searchSpace ? searchSpace.total_matches : "—"}</strong>
              <span>matching right now</span>
            </div>
          </div>
        </div>
      </header>

      <main className="app-layout">
        <aside className="app-sidebar">
          <ConversationPanel
            messages={messages}
            onSend={handleSend}
            disabled={status !== "open"}
            connectionStatus={status}
            micSupported={micSupported}
            listening={listening}
            partialTranscript={partialTranscript}
            onToggleMic={handleToggleMic}
            aiSpeaking={aiSpeaking}
            voiceEnabled={voiceEnabled}
            onToggleVoiceEnabled={() => setVoiceEnabled((v) => !v)}
          />
        </aside>

        <section className="app-main">
          <div className="status-row">
            <SearchSpaceFunnel searchSpace={searchSpace} />
            <NextQuestionExplainer discovery={discovery} />
          </div>
          <BuyerProfilePanel profile={profile} />
          <TopMatchesPanel matches={topMatches} />
        </section>
      </main>

      <footer className="app-footer">
        <p>Basera is a portfolio demo — a voice AI agent that discovers what you actually want, one question at a time.</p>
      </footer>
    </div>
  );
}

export default App;
