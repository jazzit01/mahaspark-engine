import {loadFont} from '@remotion/google-fonts/NotoSansDevanagari';

/**
 * Noto Sans Devanagari for every on-screen word. loadFont() blocks rendering until the font is
 * ready, so no frame is ever captured with a fallback font.
 */
export const {fontFamily} = loadFont('normal', {
  weights: ['500', '700', '800'],
  subsets: ['devanagari', 'latin'],
});
