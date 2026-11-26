export type ThemeName =
  | 'PrimeGridStudio'
  | 'BreakingNewsStudio'
  | 'EditorialDeskLight'
  | 'DataTelemetryStudio'
  | 'GlassNewsroomDepth'
  | 'ChalkboardStudio'
  | 'BlueprintStudio'
  | 'DataMapStudio'
  | 'AuroraStudio'
  | 'OrbitStudio'
  | 'CivicWavesStudio'
  | 'NoirSearchlightStudio'
  | 'SkyWeatherStudio'
  | 'SpeedStripesStudio'
  | 'MarketLinesStudio'
  | 'PulseCareStudio';

export type AudioMood = 'serious' | 'crime' | 'breaking' | 'upbeat' | 'neutral';

/** Footage or photo for one scene, downloaded into public/media by scripts/media_fetch.py. */
export type SceneMedia = {
  type: 'video' | 'image';
  /** Path under public/, for staticFile(). */
  file: string;
  /** Clip length in seconds (videos). */
  duration?: number;
  credit?: string;
  /** Pixel size of a still (used to pick the framed layout for landscape photos). */
  width?: number;
  height?: number;
};

/** An animated graphic for one scene, written by the editorial model and checked against the source. */
export type SceneMotion = {
  type: 'stat' | 'place' | 'quote';
  value: string;
  label?: string;
  /** Stat graphics only: which original icon (FigureIcon.tsx) to draw next to the figure. */
  icon?: string;
};

export type StoryScene = {
  headline: string;
  description: string;
  tts_text?: string;
  media?: SceneMedia;
  motion?: SceneMotion;
  /** Seconds. Written by scripts/align_timings.py. */
  start: number;
  end: number;
};

export type StoryWord = {
  text: string;
  start: number;
  end: number;
  scene: number;
};

/** The subset of remotion/public/story.json that the video reads. */
export type Story = {
  category: string;
  visual_theme: ThemeName;
  audio_mood: AudioMood;
  /** 'landscape' (16:9 video with outro, default) or 'portrait' (9:16 Short for thin stories, no outro). */
  format?: 'landscape' | 'portrait';
  /** Degrees the studio background is hue-rotated, so no two videos share one look. 0 keeps the studio colours. */
  bg_hue?: number;
  scenes: StoryScene[];
  /** what/when/who/where/why/how answers; chips on the scene cards. */
  five_w_one_h?: Record<string, string>;
  words: StoryWord[];
  /** Same timings as words, but spoken numbers merged into digits (१२, ₹१,२०० कोटी) for the screen. */
  caption_words?: StoryWord[];
  duration_seconds: number;
  /** Optional publishing cap. Only decorative tail and outro can reach this cut. */
  delivery_duration_limit?: 30 | 300;
  /** Studio previews set this to false because voiceover.wav does not exist there. */
  audio?: boolean;
  media_credits?: string[];
};
