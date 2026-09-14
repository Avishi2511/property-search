// The contract voice must satisfy, independent of which engine implements
// it. The rest of the app (App.tsx) talks only to this interface — swapping
// the browser's built-in Web Speech API for a dedicated realtime voice
// service (Deepgram, ElevenLabs, OpenAI Realtime, ...) later means writing
// one new class here, with zero changes anywhere else.
export interface VoiceProvider {
  isSupported(): boolean;

  /** Begins continuous recognition. `onPartial` fires with interim (not-yet-final)
   * text as the buyer speaks; `onFinal` fires once per completed utterance. */
  startListening(onPartial: (text: string) => void, onFinal: (text: string) => void): void;

  stopListening(): void;

  /** Speaks `text` aloud, calling `onDone` when playback finishes (or is interrupted). */
  speak(text: string, onDone?: () => void): void;

  /** Immediately stops any in-progress speech — used for barge-in when the
   * buyer starts talking while the agent is still speaking. */
  interrupt(): void;

  onListeningChange(cb: (listening: boolean) => void): void;
}
