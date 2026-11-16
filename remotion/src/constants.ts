export const COMPOSITION_ID = 'MahaSparkReel';

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;  // 16:9 landscape (was 1080x1920 vertical)

/** Central safe zone: headlines, context cards and captions live between SAFE_TOP and HEIGHT - SAFE_BOTTOM. */
export const SAFE_TOP = 175;
export const SAFE_BOTTOM = 56;
export const SAFE_SIDE = 80;

/** The same outro as the news bulletin (Outro.tsx) closes every video. */
export const OUTRO_SECONDS = 8;

/** Seconds of studio after the last spoken word. */
export const TAIL_SECONDS = 1.0;

/** A scene card appears this many frames before its first spoken word. */
export const SCENE_LEAD_FRAMES = 6;
export const SCENE_EXIT_FRAMES = 9;

/** Studio bed at -20 dB (10^(-20/20) = 0.1). */
export const BED_VOLUME = 0.1;
export const WHOOSH_VOLUME = 0.5;
/** The generated whoosh peaks about 0.2 s in; start it this many frames before the card lands. */
export const WHOOSH_LEAD_FRAMES = 6;

/** Main headline: as large as it can be for its length (a headline is at most 56 characters). */
export const headlineSize = (chars: number): number => (chars <= 22 ? 124 : chars <= 34 ? 112 : chars <= 46 ? 100 : 90);
export const DESCRIPTION_SIZE = 48; // sub-heading under the headline
export const CAPTION_SIZE = 56;
