import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {DESCRIPTION_SIZE, HEADLINE_SIZE, SAFE_SIDE, SAFE_TOP, SCENE_EXIT_FRAMES} from './constants';
import {fontFamily} from './fonts';
import {Palette} from './theme';

export type Fact = {value: string};

type Props = {
  headline: string;
  description: string;
  palette: Palette;
  /** Frames this card stays mounted (its Sequence length). */
  durationInFrames: number;
  /** 0-based scene number and scene count, for the progress row. */
  index: number;
  total: number;
  /** 5W1H chips shown for this scene (already chosen by the caller; may be empty). */
  facts: Fact[];
};

/** Space reserved below the card for the karaoke captions (px from the bottom edge). */
export const CARD_BOTTOM = 650;

/**
 * One news scene. A full-height column fills the area between the logo row and the captions:
 * progress bar, headline panel, context card and 5W1H fact chips. Spring entrances (staggered), scale/fade exit.
 */
export const SceneCard: React.FC<Props> = ({headline, description, palette, durationInFrames, index, total, facts}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 15, stiffness: 120, mass: 0.9}});
  const descEnter = spring({frame: frame - 8, fps, config: {damping: 16, stiffness: 110, mass: 0.9}});
  const factEnter = spring({frame: frame - 14, fps, config: {damping: 16, stiffness: 110, mass: 0.9}});
  const bar = interpolate(frame, [0, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const exitStart = durationInFrames - SCENE_EXIT_FRAMES;
  const exit = interpolate(frame, [exitStart, durationInFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const opacity = interpolate(enter, [0, 1], [0, 1]) * (1 - exit);
  const scale = interpolate(enter, [0, 1], [0.95, 1]) * (1 - 0.06 * exit);
  const translateY = interpolate(enter, [0, 1], [60, 0]);

  const blur = palette.cardBlur > 0 ? `blur(${palette.cardBlur}px) saturate(1.3)` : undefined;
  const shadow = palette.isLight ? '0 14px 40px rgba(15,23,42,0.14)' : '0 14px 44px rgba(0,0,0,0.38)';
  const panel: React.CSSProperties = {
    background: palette.cardBackground,
    backdropFilter: blur,
    WebkitBackdropFilter: blur,
    border: `2px solid ${palette.cardBorder}`,
    borderRadius: 24,
    boxShadow: shadow,
  };
  const staged = (e: number): React.CSSProperties => ({
    opacity: interpolate(e, [0, 1], [0, 1]),
    transform: `translateY(${interpolate(e, [0, 1], [34, 0])}px)`,
  });

  const longHeadline = headline.length > 44;
  const showFacts = facts.length > 0;

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
      <div style={{display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0}}>
        <div style={{display: 'flex', gap: 8, flex: 1}}>
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
      </div>

      {/* Headline panel with the animated vertical accent bar */}
      <div style={{...panel, flex: showFacts ? 1.7 : 1.5, minHeight: 0, display: 'flex', alignItems: 'stretch', gap: 28, padding: '34px 36px 34px 30px'}}>
        <div style={{width: 12, flexShrink: 0, borderRadius: 6, background: palette.accent, transformOrigin: 'top center', transform: `scaleY(${bar})`}} />
        <div style={{flex: 1, display: 'flex', alignItems: 'center', minWidth: 0}}>
          <div
            style={{
              color: palette.textPrimary,
              fontSize: longHeadline ? HEADLINE_SIZE - 2 : HEADLINE_SIZE + 2,
              fontWeight: 800,
              lineHeight: 1.28,
              letterSpacing: -0.3,
              textShadow: palette.textShadow,
              overflowWrap: 'break-word',
            }}
          >
            {headline}
          </div>
        </div>
      </div>

      {/* Context card */}
      <div style={{...panel, ...staged(descEnter), flex: 1, minHeight: 200, display: 'flex', alignItems: 'center', padding: '28px 36px'}}>
        <div
          style={{
            color: palette.textSecondary,
            fontSize: DESCRIPTION_SIZE,
            fontWeight: 700,
            lineHeight: 1.45,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {description}
        </div>
      </div>

      {/* 5W1H fact chips */}
      {showFacts ? (
        <div style={{...staged(factEnter), display: 'grid', gridTemplateColumns: facts.length > 1 ? '1fr 1fr' : '1fr', gap: 18, flexShrink: 0}}>
          {facts.map((fact) => (
            <div key={fact.value} style={{...panel, borderRadius: 20, padding: '22px 26px', borderLeft: `8px solid ${palette.accent2}`, minWidth: 0, display: 'flex', alignItems: 'center'}}>
              <div
                style={{
                  color: palette.textPrimary,
                  fontSize: 38,
                  fontWeight: 700,
                  lineHeight: 1.35,
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {fact.value}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};
