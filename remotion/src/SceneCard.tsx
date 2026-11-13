import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {DESCRIPTION_SIZE, HEADLINE_SIZE, SAFE_SIDE, SAFE_TOP, SCENE_EXIT_FRAMES} from './constants';
import {fontFamily} from './fonts';
import {Palette} from './theme';

type Props = {
  headline: string;
  description: string;
  palette: Palette;
  /** Frames this card stays mounted (its Sequence length). */
  durationInFrames: number;
};

/** One news scene: spring entrance, animated accent bar, bold headline, two-line context card, scale/fade exit. */
export const SceneCard: React.FC<Props> = ({headline, description, palette, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 15, stiffness: 120, mass: 0.9}});
  const descEnter = spring({frame: frame - 8, fps, config: {damping: 16, stiffness: 110, mass: 0.9}});
  const bar = interpolate(frame, [0, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const exitStart = durationInFrames - SCENE_EXIT_FRAMES;
  const exit = interpolate(frame, [exitStart, durationInFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const opacity = interpolate(enter, [0, 1], [0, 1]) * (1 - exit);
  const scale = interpolate(enter, [0, 1], [0.94, 1]) * (1 - 0.06 * exit);
  const translateY = interpolate(enter, [0, 1], [70, 0]);
  const descOpacity = interpolate(descEnter, [0, 1], [0, 1]);
  const descY = interpolate(descEnter, [0, 1], [34, 0]);

  const blur = palette.cardBlur > 0 ? `blur(${palette.cardBlur}px) saturate(1.3)` : undefined;

  return (
    <div
      style={{
        position: 'absolute',
        left: SAFE_SIDE,
        right: SAFE_SIDE,
        top: SAFE_TOP + 40,
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        transformOrigin: '50% 40%',
        fontFamily,
      }}
    >
      {/* Headline block with the animated vertical accent bar */}
      <div style={{display: 'flex', alignItems: 'stretch', gap: 28}}>
        <div style={{width: 12, flexShrink: 0, borderRadius: 6, background: palette.accent, alignSelf: 'stretch', transformOrigin: 'top center', transform: `scaleY(${bar})`}} />
        <div
          style={{
            color: palette.textPrimary,
            fontSize: HEADLINE_SIZE,
            fontWeight: 800,
            lineHeight: 1.28,
            letterSpacing: -0.3,
            textShadow: palette.textShadow,
            wordBreak: 'keep-all',
            overflowWrap: 'break-word',
          }}
        >
          {headline}
        </div>
      </div>

      {/* Two-line context card */}
      <div
        style={{
          marginTop: 38,
          opacity: descOpacity,
          transform: `translateY(${descY}px)`,
          background: palette.cardBackground,
          backdropFilter: blur,
          WebkitBackdropFilter: blur,
          border: `2px solid ${palette.cardBorder}`,
          borderRadius: 22,
          padding: '30px 36px 34px',
          boxShadow: palette.isLight ? '0 14px 40px rgba(15,23,42,0.14)' : '0 14px 44px rgba(0,0,0,0.38)',
        }}
      >
        <div
          style={{
            color: palette.textSecondary,
            fontSize: DESCRIPTION_SIZE,
            fontWeight: 700,
            lineHeight: 1.42,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {description}
        </div>
      </div>
    </div>
  );
};
