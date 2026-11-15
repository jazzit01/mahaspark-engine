import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {DESCRIPTION_SIZE, headlineSize, SAFE_SIDE, SAFE_TOP, SCENE_EXIT_FRAMES} from './constants';
import {fontFamily} from './fonts';
import {MotionGraphic} from './MotionGraphic';
import {Palette} from './theme';
import {SceneMotion} from './types';

type Props = {
  headline: string;
  description: string;
  palette: Palette;
  /** Frames this card stays mounted (its Sequence length). */
  durationInFrames: number;
  /** 0-based scene number and scene count, for the progress bar. */
  index: number;
  total: number;
  /** Optional animated graphic (figure, place or quote) for this scene. */
  motion?: SceneMotion;
};

/** Space reserved below the card for the karaoke captions (px from the bottom edge). */
export const CARD_BOTTOM = 650;

/**
 * One news scene: progress bar on top, then a vertically centred stack of the big main headline, the context
 * line as a sub-heading and, when the story supports one, an animated graphic. Spring entrances (staggered),
 * scale/fade exit. No boxes: the text sits directly on the studio or on the dimmed footage.
 */
export const SceneCard: React.FC<Props> = ({headline, description, palette, durationInFrames, index, total, motion}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 15, stiffness: 120, mass: 0.9}});
  const subEnter = spring({frame: frame - 8, fps, config: {damping: 16, stiffness: 110, mass: 0.9}});
  const bar = interpolate(frame, [0, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const exitStart = durationInFrames - SCENE_EXIT_FRAMES;
  const exit = interpolate(frame, [exitStart, durationInFrames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const opacity = interpolate(enter, [0, 1], [0, 1]) * (1 - exit);
  const scale = interpolate(enter, [0, 1], [0.95, 1]) * (1 - 0.06 * exit);
  const translateY = interpolate(enter, [0, 1], [60, 0]);
  const staged = (e: number): React.CSSProperties => ({
    opacity: interpolate(e, [0, 1], [0, 1]),
    transform: `translateY(${interpolate(e, [0, 1], [34, 0])}px)`,
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: SAFE_SIDE,
        right: SAFE_SIDE,
        top: SAFE_TOP + 6,
        bottom: CARD_BOTTOM,
        display: 'flex',
        flexDirection: 'column',
        gap: 24,
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        transformOrigin: '50% 40%',
        fontFamily,
      }}
    >
      {/* Progress bar: one segment per scene */}
      <div style={{display: 'flex', gap: 8, flexShrink: 0}}>
        {Array.from({length: total}).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 8,
              borderRadius: 4,
              background: i <= index ? palette.accent : palette.cardBorder,
              opacity: i === index ? 1 : i < index ? 0.85 : 0.5,
            }}
          />
        ))}
      </div>

      {/* Headline, sub-heading and graphic, centred in the remaining height */}
      <div style={{flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 30}}>
        <div style={{display: 'flex', alignItems: 'stretch', gap: 30}}>
          <div style={{width: 14, flexShrink: 0, borderRadius: 7, background: palette.accent, transformOrigin: 'top center', transform: `scaleY(${bar})`}} />
          <div
            style={{
              flex: 1,
              minWidth: 0,
              color: palette.textPrimary,
              fontSize: headlineSize(headline.length),
              fontWeight: 800,
              lineHeight: 1.22,
              letterSpacing: -0.4,
              textShadow: palette.textShadow,
              overflowWrap: 'break-word',
            }}
          >
            {headline}
          </div>
        </div>

        <div
          style={{
            ...staged(subEnter),
            marginLeft: 44,
            color: palette.textSecondary,
            fontSize: DESCRIPTION_SIZE,
            fontWeight: 600,
            lineHeight: 1.45,
            textShadow: palette.textShadow,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {description}
        </div>

        {motion ? <MotionGraphic motion={motion} palette={palette} delay={16} /> : null}
      </div>
    </div>
  );
};
