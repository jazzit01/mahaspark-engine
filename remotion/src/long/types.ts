export type LongWord = {text: string; start: number; end: number};

export type LongMedia = {file: string; width: number; height: number};

export type LongItem = {
  label: string;
  value?: string;
  /** Seconds from the start of the scene at which this item appears (the word that names it is spoken). */
  cue: number;
};

export type LongSceneKind =
  | 'title' | 'points' | 'steps' | 'compare' | 'timeline' | 'stat' | 'quote' | 'summary' | 'chart'
  | 'quiz_intro' | 'question' | 'answer' | 'quiz_end';

export type LongScene = {
  kind: LongSceneKind;
  headline: string;
  subtitle?: string;
  items: LongItem[];
  audio: string; // path inside remotion/public
  audio_seconds: number;
  lead_seconds: number;
  /** Silent seconds after the voice (the quiz countdown). */
  extra_seconds?: number;
  /** Seconds the whole scene lasts, and where it starts in the video. */
  seconds: number;
  start: number;
  /** Spoken words with times in seconds from the start of the scene (numbers merged into Devanagari digits). */
  words: LongWord[];
  // quiz
  q_index?: number;
  total?: number;
  correct?: number;
  /** A real photo of the topic behind this scene (explainer only), path inside remotion/public. */
  media?: LongMedia;
  reveal_at?: number;
  explain_at?: number;
};

/** A place shown as a pulsing pin on the Maharashtra map (explainer title scene). */
export type GeoPin = {lat: number; lon: number; label: string};

export type LongProps = {
  kind: 'explainer' | 'quiz';
  title: string;
  audio_mood: 'serious' | 'crime' | 'breaking' | 'upbeat' | 'neutral';
  bg_hue?: number;
  /** Which animated studio runs behind the video (one per video). */
  studio?: string;
  /** Brand style pack: knowledge (explainer) | quiz | news. Sets the accent colours. */
  pack?: string;
  /** Optional looping background clip (path inside remotion/public, e.g. loops/x.mp4). */
  loop?: string | null;
  credits?: string[];
  /** Where the topic is, when it is a place in Maharashtra (from scripts/geo.py). */
  map?: GeoPin;
  /** Shorts cut: only this part (seconds) of the video is shown, vertical, no outro. */
  clip?: {start: number; end: number};
  scenes: LongScene[];
  outro_seconds: number;
  outro_start: number;
  total_seconds: number;
};
