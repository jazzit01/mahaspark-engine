import React from 'react';
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FigureIcon} from './FigureIcon';
import {Palette} from './theme';
import {SceneMotion} from './types';

type Props = {
  motion: SceneMotion;
  palette: Palette;
  /** Frames after the scene starts before the graphic begins to animate. */
  delay: number;
};

const NUMBER = /([\d०-९][\d०-९,]*(?:\.[\d०-९]+)?)/;
const DEVA = '०१२३४५६७८९';
/** Devanagari digits to Latin so the count-up can be computed. */
const toLatin = (text: string) => text.replace(/[०-९]/g, (d) => String(DEVA.indexOf(d)));
/** Latin digits to Devanagari for display. */
const toDeva = (text: string) => text.replace(/\d/g, (d) => DEVA[Number(d)]);

const useEntrance = (delay: number) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - delay);
  const enter = spring({frame: local, fps, config: {damping: 14, stiffness: 120, mass: 0.8}});
  return {local, enter};
};

/** A key figure: counts up from zero (with a filling bar for percentages). */
const Stat: React.FC<Props> = ({motion, palette, delay}) => {
  const {local, enter} = useEntrance(delay);
  const {width, height} = useVideoConfig();
  const wide = width > height;
  const match = NUMBER.exec(motion.value);
  const target = match ? parseFloat(toLatin(match[1]).replace(/,/g, '')) : 0;
  const decimals = match && match[1].includes('.') ? match[1].split('.')[1].length : 0;
  const prefix = match ? motion.value.slice(0, match.index) : '';
  const suffix = match ? motion.value.slice(match.index + match[1].length) : motion.value;
  const progress = interpolate(local, [0, 42], [0, 1], {easing: Easing.out(Easing.cubic), extrapolateRight: 'clamp'});
  const shown = toDeva((target * progress).toLocaleString('en-IN', {minimumFractionDigits: decimals, maximumFractionDigits: decimals}));
  const isPercent = motion.value.includes('%');

  const icon = (
    <FigureIcon icon={motion.icon} local={local} color={palette.accent} color2={palette.accent2} percent={isPercent ? target : 0} size={wide ? 170 : 120} />
  );
  const figure = (
    <div style={{minWidth: 0}}>
      <div style={{display: 'flex', alignItems: 'baseline', gap: 14, color: palette.accent, textShadow: palette.textShadow}}>
        {prefix ? <span style={{fontSize: 64, fontWeight: 800}}>{prefix}</span> : null}
        <span style={{fontSize: 132, fontWeight: 800, lineHeight: 1, letterSpacing: -2}}>{match ? shown : motion.value}</span>
        {match && suffix ? <span style={{fontSize: 58, fontWeight: 800, color: palette.textPrimary}}>{suffix}</span> : null}
      </div>
      {motion.label ? (
        <div style={{marginTop: 8, fontSize: 38, fontWeight: 700, color: palette.textPrimary, textShadow: palette.textShadow}}>{motion.label}</div>
      ) : null}
    </div>
  );

  // wide video: icon beside the figure; vertical video: icon above it (the figure needs the full width)
  return (
    <div
      style={{
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [30, 0])}px)`,
        marginLeft: 44,
        display: 'flex',
        flexDirection: wide ? 'row' : 'column',
        alignItems: wide ? 'center' : 'flex-start',
        gap: wide ? 36 : 10,
      }}
    >
      {icon}
      {figure}
    </div>
  );
};

/** A place: a pulsing map pin with ripples and the place name. */
const Place: React.FC<Props> = ({motion, palette, delay}) => {
  const {local, enter} = useEntrance(delay);
  const drop = interpolate(enter, [0, 1], [-70, 0]);
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 26, marginLeft: 44, opacity: interpolate(enter, [0, 0.4], [0, 1], {extrapolateRight: 'clamp'})}}>
      <div style={{position: 'relative', width: 120, height: 120, flexShrink: 0}}>
        {[0, 1, 2].map((i) => {
          const t = ((local - 14 + i * 20) % 60) / 60;
          const live = local > 14 && t >= 0;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: 60 - 20 - t * 40,
                top: 96 - 12 - t * 12,
                width: 40 + t * 80,
                height: 24 + t * 24,
                borderRadius: '50%',
                border: `4px solid ${palette.accent2}`,
                opacity: live ? 0.85 * (1 - t) : 0,
              }}
            />
          );
        })}
        <svg width="120" height="120" viewBox="0 0 120 120" style={{position: 'absolute', left: 0, top: drop}}>
          <path d="M60 8C41 8 27 22 27 41c0 24 33 55 33 55s33-31 33-55C93 22 79 8 60 8z" fill={palette.accent} />
          <circle cx="60" cy="41" r="13" fill={palette.isLight ? '#fff' : '#0B1220'} />
        </svg>
      </div>
      <div
        style={{
          fontSize: 70,
          fontWeight: 800,
          color: palette.textPrimary,
          textShadow: palette.textShadow,
          borderBottom: `6px solid ${palette.accent}`,
          paddingBottom: 4,
          clipPath: `inset(0 ${interpolate(local, [6, 26], [100, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}% 0 0)`,
        }}
      >
        {motion.value}
      </div>
    </div>
  );
};

/** A quotation: large quote mark, the exact words and the speaker. */
const Quote: React.FC<Props> = ({motion, palette, delay}) => {
  const {local, enter} = useEntrance(delay);
  const speaker = interpolate(local, [18, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{display: 'flex', gap: 22, marginLeft: 44, opacity: enter, transform: `translateY(${interpolate(enter, [0, 1], [30, 0])}px)`}}>
      <div style={{fontSize: 170, lineHeight: 0.8, fontWeight: 800, color: palette.accent, textShadow: palette.textShadow, flexShrink: 0}}>“</div>
      <div style={{minWidth: 0}}>
        <div
          style={{
            fontSize: 46,
            fontWeight: 700,
            lineHeight: 1.4,
            color: palette.textPrimary,
            textShadow: palette.textShadow,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {motion.value}
        </div>
        {motion.label ? (
          <div style={{marginTop: 14, display: 'flex', alignItems: 'center', gap: 16, opacity: speaker}}>
            <div style={{width: 56 * speaker, height: 6, borderRadius: 3, background: palette.accent}} />
            <div style={{fontSize: 38, fontWeight: 800, color: palette.accent, textShadow: palette.textShadow}}>{motion.label}</div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const MotionGraphic: React.FC<Props> = (props) => {
  switch (props.motion.type) {
    case 'stat':
      return <Stat {...props} />;
    case 'place':
      return <Place {...props} />;
    case 'quote':
      return <Quote {...props} />;
    default:
      return null;
  }
};
