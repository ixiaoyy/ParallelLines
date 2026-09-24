export interface ClearSound {
  play(): void;
  stop(): void;
  dispose(): void;
}
export function createClearSound(): ClearSound {
  let context: AudioContext | null = null;
  const active = new Set<OscillatorNode>();

  function getContext(): AudioContext | null {
    try {
      context ??= new AudioContext();
      return context;
    } catch {
      return null;
    }
  }

  function stop(): void {
    for (const oscillator of active) {
      try {
        oscillator.stop();
      } catch {
        // The node may already have completed naturally.
      }
    }
    active.clear();
    void context?.suspend().catch(() => undefined);
  }

  function play(): void {
    const audio = getContext();
    if (!audio) return;
    void audio.resume().then(() => {
      const now = audio.currentTime;
      const oscillator = audio.createOscillator();
      const gain = audio.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(480, now);
      oscillator.frequency.exponentialRampToValueAtTime(720, now + 0.16);
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.06, now + 0.025);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.24);
      oscillator.connect(gain).connect(audio.destination);
      active.add(oscillator);
      oscillator.addEventListener("ended", () => active.delete(oscillator), {
        once: true,
      });
      oscillator.start(now);
      oscillator.stop(now + 0.25);
    }).catch(() => undefined);
  }

  function dispose(): void {
    stop();
    void context?.close().catch(() => undefined);
    context = null;
  }

  return { play, stop, dispose };
}
