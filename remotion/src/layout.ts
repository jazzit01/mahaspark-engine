import {useVideoConfig} from 'remotion';

/** Everything that differs between the 16:9 video and the 9:16 Short. Picked from the composition size. */
export type Layout = {
  landscape: boolean;
  safeTop: number;
  safeBottom: number;
  safeSide: number;
  /** Space reserved under the scene card for the karaoke captions. */
  cardBottom: number;
  descriptionSize: number;
  captionSize: number;
  captionMaxWidth: number;
  logo: {left: number; top: number; width: number; height: number};
  headlineSize: (chars: number) => number;
};

export const LANDSCAPE: Layout = {
  landscape: true,
  safeTop: 175,
  safeBottom: 56,
  safeSide: 80,
  cardBottom: 250,
  descriptionSize: 48,
  captionSize: 56,
  captionMaxWidth: 1500,
  logo: {left: 40, top: 26, width: 230, height: 140},
  headlineSize: (chars) => (chars <= 22 ? 124 : chars <= 34 ? 112 : chars <= 46 ? 100 : 90),
};

/** The original vertical reel layout (1080x1920), unchanged. */
export const PORTRAIT: Layout = {
  landscape: false,
  safeTop: 290,
  safeBottom: 450,
  safeSide: 60,
  cardBottom: 650,
  descriptionSize: 46,
  captionSize: 52,
  captionMaxWidth: 960,
  logo: {left: 34, top: 34, width: 300, height: 200},
  headlineSize: (chars) => (chars <= 22 ? 108 : chars <= 34 ? 100 : chars <= 46 ? 92 : 84),
};

export const layoutFor = (width: number, height: number): Layout => (width >= height ? LANDSCAPE : PORTRAIT);

export const useLayout = (): Layout => {
  const {width, height} = useVideoConfig();
  return layoutFor(width, height);
};
