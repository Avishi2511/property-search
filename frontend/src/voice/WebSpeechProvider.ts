import type { VoiceProvider } from "./VoiceProvider";

const LANG = "en-IN";

/**
 * Browser-native implementation of VoiceProvider: SpeechRecognition for STT,
 * speechSynthesis for TTS. Zero API keys, genuinely streaming (interim
 * results arrive as the buyer talks), and supports barge-in — recognition
 * stays active while the agent speaks, so any incoming speech immediately
 * cancels playback.
 *
 * Known limitation: without headphones, the mic can pick up the agent's own
 * voice from the speakers. Chrome's default mic capture applies some echo
 * cancellation, which usually keeps this from causing false interrupts, but
 * it isn't guaranteed — a real deployment would route audio through a
 * proper acoustic-echo-cancelling pipeline (which is exactly what a
 * dedicated realtime voice API like the ones this interface can be swapped
 * to would provide, per DEFAULT_CONFIG's note in the project's voice
 * strategy).
 */
export class WebSpeechProvider implements VoiceProvider {
  private recognition: SpeechRecognitionLike | null = null;
  private onListeningChangeCb: ((listening: boolean) => void) | null = null;
  private shouldBeListening = false;

  constructor() {
    const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Ctor) return;

    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = LANG;
    this.recognition = recognition;

    recognition.onend = () => {
      // Chrome auto-stops recognition after periods of silence even in
      // continuous mode; restart transparently if the user hasn't
      // explicitly turned the mic off.
      this.onListeningChangeCb?.(false);
      if (this.shouldBeListening) {
        try {
          recognition.start();
          this.onListeningChangeCb?.(true);
        } catch {
          // Already starting; ignore.
        }
      }
    };

    recognition.onerror = () => {
      this.shouldBeListening = false;
      this.onListeningChangeCb?.(false);
    };
  }

  isSupported(): boolean {
    return this.recognition !== null && "speechSynthesis" in window;
  }

  startListening(onPartial: (text: string) => void, onFinal: (text: string) => void): void {
    if (!this.recognition) return;

    this.recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        if (result.isFinal) {
          onFinal(transcript.trim());
        } else {
          interim += transcript;
        }
      }
      if (interim.trim()) {
        onPartial(interim.trim());
        // The buyer has started talking — barge in over the agent.
        if (window.speechSynthesis.speaking) {
          window.speechSynthesis.cancel();
        }
      }
    };

    this.shouldBeListening = true;
    try {
      this.recognition.start();
      this.onListeningChangeCb?.(true);
    } catch {
      // Already listening; ignore.
    }
  }

  stopListening(): void {
    this.shouldBeListening = false;
    this.recognition?.stop();
    this.onListeningChangeCb?.(false);
  }

  speak(text: string, onDone?: () => void): void {
    window.speechSynthesis.cancel(); // clear anything queued/playing first
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = LANG;
    utterance.rate = 1.0;
    utterance.onend = () => onDone?.();
    utterance.onerror = () => onDone?.();
    window.speechSynthesis.speak(utterance);
  }

  interrupt(): void {
    window.speechSynthesis.cancel();
  }

  onListeningChange(cb: (listening: boolean) => void): void {
    this.onListeningChangeCb = cb;
  }
}
