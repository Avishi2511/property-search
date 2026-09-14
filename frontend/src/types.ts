// Mirrors the JSON shapes produced by backend/app/api/ws.py.

export type ConstraintType = "hard" | "soft" | "preference" | "context";

export interface ConstraintValue {
  value: unknown;
  min: number | null;
  max: number | null;
  previous: unknown;
  changed: boolean;
  confidence: number;
  type: ConstraintType;
  source_turn: number;
  updated_at_turn: number;
}

export interface Profile {
  buyer_id: string;
  constraints: Record<string, ConstraintValue>;
  unknowns: string[];
  turn_count: number;
}

export interface TopMatch {
  id: string;
  project: string;
  location: string;
  price: number;
  bedrooms: number;
  area_sqft: number;
  possession: string;
  builder: string;
  amenities: string[];
  score: number;
  breakdown: Record<string, number>;
}

export interface QuestionSelection {
  field: string;
  question_text: string;
  score: number;
  estimated_reduction_pct: number;
  reason: string;
}

export interface DiscoveryDecision {
  should_stop: boolean;
  next_question: QuestionSelection | null;
  stop_reason: string | null;
  candidate_count: number;
}

export interface SearchSpace {
  total_matches: number;
  history: number[];
}

export interface AppliedUpdate {
  turn: number;
  field: string;
  old_value: unknown;
  new_value: unknown;
  reason: "new_info" | "correction" | "refinement" | "confirmation";
}

export interface InitMessage {
  type: "init";
  profile: Profile;
  search_space: SearchSpace;
}

export interface TurnUpdateMessage {
  type: "turn_update";
  turn: number;
  response_text: string;
  profile: Profile;
  search_space: SearchSpace;
  top_matches: TopMatch[];
  discovery: DiscoveryDecision;
  applied_updates: AppliedUpdate[];
  questions_asked: number;
}

export type ServerMessage = InitMessage | TurnUpdateMessage;

export interface ChatMessage {
  role: "buyer" | "ai";
  text: string;
}
