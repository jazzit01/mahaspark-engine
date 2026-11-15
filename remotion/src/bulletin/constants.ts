export const BULLETIN_WIDTH = 1920;
export const BULLETIN_HEIGHT = 1080;
export const TICKER_HEIGHT = 96;
export const PHOTO_WIDTH = 870;
export const PHOTO_CUT = 150; // horizontal run of the diagonal cut line
export const TEXT_LEFT = 72;
export const TEXT_WIDTH = 960;
export const COLORS = {
  bgTop: '#0a1736',
  bgBottom: '#050a16',
  grid: 'rgba(120,160,255,0.07)',
  gold: '#f5c451',
  red: '#e11d2e',
  white: '#ffffff',
  context: '#cfd9f0',
  ticker: '#0b1327',
};
export const CHANNEL_HANDLE = '@MahaSparkOfficial';
export const TRANSITION_FRAMES = 16;
export const WHOOSH_FRAMES_EARLY = 4;

/** Headline size by length: the text is sized to fill the left column, never to be timid. */
export const headlineSize = (text: string): number => {
  const n = text.length;
  if (n <= 20) return 140;
  if (n <= 30) return 124;
  if (n <= 40) return 108;
  return 96;
};

/** Frame length of each item, and the outro after them. Item starts are the running sum. */
export const itemFrames = (seconds: number, fps: number): number => Math.max(1, Math.round(seconds * fps));
