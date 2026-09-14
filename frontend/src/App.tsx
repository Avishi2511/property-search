import { useEffect, useRef, useState } from "react";
import { BuyerProfilePanel } from "./components/BuyerProfilePanel";
import { ConversationPanel } from "./components/ConversationPanel";
import { NextQuestionExplainer } from "./components/NextQuestionExplainer";
import { SearchSpaceFunnel } from "./components/SearchSpaceFunnel";
import { TopMatchesPanel } from "./components/TopMatchesPanel";
import type { ChatMessage, DiscoveryDecision, Profile, SearchSpace, TopMatch } from "./types";
import { connectConversationSocket, type ConversationSocket } from "./ws/client";

function App() {
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [searchSpace, setSearchSpace] = useState<SearchSpace | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryDecision | null>(null);
  const [topMatches, setTopMatches] = useState<TopMatch[]>([]);
  const socketRef = useRef<ConversationSocket | null>(null);

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
      }
    }, setStatus);

    socketRef.current = socket;
    return () => socket.close();
  }, []);

  function handleSend(text: string) {
    setMessages((prev) => [...prev, { role: "buyer", text }]);
    socketRef.current?.sendUtterance(text);
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
