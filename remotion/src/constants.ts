export const COMPOSITION_ID = 'MahaSparkReel';

export const FPS = 30;
export const WIDTH = 1080;
export const HEIGHT = 1920;

/** Central safe zone: headlines, context cards and captions live between SAFE_TOP and HEIGHT - SAFE_BOTTOM. */
export const SAFE_TOP = 290;
export const SAFE_BOTTOM = 450;
export const SAFE_SIDE = 60;

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

export const HEADLINE_SIZE = 74; // spec: 72-76px bold
export const DESCRIPTION_SIZE = 40; // spec: 38-40px
export const CAPTION_SIZE = 52;
