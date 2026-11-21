export type LongWord = {text: string; start: number; end: number};

export type LongItem = {
  label: string;
  value?: string;
  /** Seconds from the start of the scene at which this item appears (the word that names it is spoken). */
  cue: number;
};

export type LongSceneKind =
  | 'title' | 'points' | 'steps' | 'compare' | 'timeline' | 'stat' | 'quote' | 'summary'
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
  media?: {file: string; width: number; height: number};
  reveal_at?: number;
  explain_at?: number;
};

export type LongProps = {
  kind: 'explainer' | 'quiz';
  title: string;
  audio_mood: 'serious' | 'crime' | 'breaking' | 'upbeat' | 'neutral';
  bg_hue?: number;
  /** Which animated studio runs behind the video (one per video). */
  studio?: string;
  credits?: string[];
  scenes: LongScene[];
  outro_seconds: number;
  outro_start: number;
  total_seconds: number;
};
