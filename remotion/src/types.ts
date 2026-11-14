export type ThemeName =
  | 'PrimeGridStudio'
  | 'BreakingNewsStudio'
  | 'EditorialDeskLight'
  | 'DataTelemetryStudio'
  | 'GlassNewsroomDepth';

export type AudioMood = 'serious' | 'crime' | 'breaking' | 'upbeat' | 'neutral';

export type StoryScene = {
  headline: string;
  description: string;
  tts_text?: string;
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
  scenes: StoryScene[];
  /** what/when/who/where/why/how answers; chips on the scene cards. */
  five_w_one_h?: Record<string, string>;
  words: StoryWord[];
  duration_seconds: number;
  /** Studio previews set this to false because voiceover.wav does not exist there. */
  audio?: boolean;
};
