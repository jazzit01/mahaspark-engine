import React from 'react';
import {interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {Palette} from './theme';
import {StoryWord} from './types';

type Props = {
  palette: Palette;
  /** Spoken word timings of the whole story (absolute seconds). */
  words: StoryWord[];
  /** Frame at which this scene starts inside the story, to turn the local frame into story time. */
  startFrame: number;
  /** Scene number, only to give every scene its own drift directions. */
  index: number;
  /** Footage or a photo sits behind this scene: keep the effect gentler so the picture stays clean. */
  overMedia: boolean;
};

const SWEEP_START = 6;
const SWEEP_FRAMES = 44;

/** 0 while nobody speaks, up to 1 on a spoken word, easing out over 0.35 s of silence. A continuous function of
 *  time (distance to the nearest word), so the glow breathes with the voice and never flickers. */
export const speechEnvelope = (words: StoryWord[], t: number): number => {
  let nearest = 1;
  for (const w of words) {
    const d = t < w.start ? w.start - t : t > w.end ? t - w.end : 0;
    if (d < nearest) nearest = d;
    if (nearest === 0) break;
  }
  return interpolate(nearest, [0, 0.35], [1, 0], {extrapolateRight: 'clamp'});
};

const radial = (color: string, opacity: number, size: number, x: number, y: number): React.CSSProperties => ({
  position: 'absolute',
  left: x - size / 2,
  top: y - size / 2,
  width: size,
  height: size,
  borderRadius: '50%',
  background: color,
  opacity,
  WebkitMaskImage: 'radial-gradient(circle, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 68%)',
  maskImage: 'radial-gradient(circle, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 68%)',
});

/**
 * Motion that sits behind the headline: two soft colour glows drifting at different speeds (a slow parallax), one
 * light sweep that crosses the frame as the scene arrives, and a warm glow right behind the text that swells with
 * the anchor's voice. Pure CSS gradients (cheap to render), no text, no assets.
 */
export const HeadlineMotion: React.FC<Props> = ({palette, words, startFrame, index, overMedia}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = (startFrame + frame) / fps;
  const gentle = overMedia ? 0.55 : 1;
  const dir = index % 2 === 0 ? 1 : -1;

  const orbA = {
    x: width * (0.25 + 0.5 * random(`ha${index}`)) + Math.sin(t * 0.21) * width * 0.06 * dir,
    y: height * (0.30 + 0.12 * random(`hb${index}`)) + Math.cos(t * 0.17) * height * 0.025,
  };
  const orbB = {
    x: width * (0.55 + 0.35 * random(`hc${index}`)) - Math.sin(t * 0.33) * width * 0.09 * dir,
    y: height * (0.52 + 0.14 * random(`hd${index}`)) - Math.cos(t * 0.27) * height * 0.03,
  };

  const sweepProgress = interpolate(frame, [SWEEP_START, SWEEP_START + SWEEP_FRAMES], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const sweepX = interpolate(sweepProgress, [0, 1], [-0.3, 1.2]) * width;
  const sweepAlpha = Math.sin(Math.PI * sweepProgress) * 0.16 * gentle;

  const voice = speechEnvelope(words, t);
  const glow = (0.05 + 0.15 * voice) * gentle;
  const glowSize = Math.min(width, height) * 1.15;

  return (
    <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden'}}>
      <div style={radial(palette.accent2, 0.10 * gentle, width * 0.95, orbA.x, orbA.y)} />
      <div style={radial(palette.accent, 0.08 * gentle, width * 0.8, orbB.x, orbB.y)} />
      <div style={radial(palette.accent, glow, glowSize, width / 2, height * 0.45)} />
      {sweepAlpha > 0.002 ? (
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: sweepX - width * 0.12,
            width: width * 0.24,
            background: 'linear-gradient(100deg, rgba(255,255,255,0) 0%, rgba(255,255,255,1) 50%, rgba(255,255,255,0) 100%)',
            opacity: sweepAlpha,
            transform: 'skewX(-14deg)',
          }}
        />
      ) : null}
    </div>
  );
};
