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

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Voice Search With Progressive Constraint Discovery</h1>
        <p>The agent decides what to ask next based on what would most narrow your property search.</p>
      </header>

      <main className="app-layout">
        <div className="app-column app-column-left">
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
        </div>

        <div className="app-column app-column-right">
          <BuyerProfilePanel profile={profile} />
          <SearchSpaceFunnel searchSpace={searchSpace} />
          <NextQuestionExplainer discovery={discovery} />
          <TopMatchesPanel matches={topMatches} />
        </div>
      </main>
    </div>
  );
}

export default App;
