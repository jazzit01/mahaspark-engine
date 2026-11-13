import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {HEIGHT, WIDTH} from '../constants';

const wavePath = (frame: number, base: number, amp: number, k: number, speed: number, phase: number): string => {
  const points: string[] = [];
  for (let x = 0; x <= WIDTH; x += 20) {
    const y = base + amp * Math.sin(x * k + frame * speed + phase);
    points.push(`${x === 0 ? 'M' : 'L'}${x},${y.toFixed(1)}`);
  }
  return points.join(' ');
};

const Bracket: React.FC<{corner: 'tl' | 'tr' | 'bl' | 'br'}> = ({corner}) => {
  const size = 90;
  const base: React.CSSProperties = {position: 'absolute', width: size, height: size, borderColor: '#F59E0B', borderStyle: 'solid', borderWidth: 0};
  const sides: Record<string, React.CSSProperties> = {
    tl: {top: 22, left: 22, borderTopWidth: 8, borderLeftWidth: 8},
    tr: {top: 22, right: 22, borderTopWidth: 8, borderRightWidth: 8},
    bl: {bottom: 22, left: 22, borderBottomWidth: 8, borderLeftWidth: 8},
    br: {bottom: 22, right: 22, borderBottomWidth: 8, borderRightWidth: 8},
  };
  return <div style={{...base, ...sides[corner]}} />;
};

/** Dark charcoal studio with crimson kinetic light waves, moving scanlines and urgent crimson/amber framing. */
export const BreakingNewsStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const pulse = 1 + 0.18 * Math.sin(t * 2.2);
  const framePulse = 0.55 + 0.25 * Math.sin(t * 5.5);
  const scanBarY = ((t * 340) % (HEIGHT + 500)) - 250;
  const lineShift = (frame * 2) % 7;

  const waves = [
    {base: 520, amp: 70, k: 0.006, speed: 0.045, phase: 0, width: 5, opacity: 0.55},
    {base: 760, amp: 95, k: 0.0045, speed: -0.035, phase: 1.7, width: 4, opacity: 0.4},
    {base: 1180, amp: 80, k: 0.0055, speed: 0.05, phase: 3.1, width: 5, opacity: 0.45},
    {base: 1420, amp: 60, k: 0.007, speed: -0.04, phase: 4.6, width: 3, opacity: 0.35},
  ];

  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #121218 0%, #0B0B0F 55%, #070709 100%)'}}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at 50% 38%, rgba(225,29,72,${0.2 * pulse}) 0%, transparent 62%)`,
        }}
      />

      <svg width={WIDTH} height={HEIGHT} style={{position: 'absolute', left: 0, top: 0, filter: 'blur(10px)'}}>
        {waves.map((w, i) => (
          <path
            key={`glow-${i}`}
            d={wavePath(frame, w.base, w.amp * pulse, w.k, w.speed, w.phase)}
            stroke="#E11D48"
            strokeWidth={w.width * 4}
            strokeOpacity={w.opacity * 0.55}
            fill="none"
          />
        ))}
      </svg>
      <svg width={WIDTH} height={HEIGHT} style={{position: 'absolute', left: 0, top: 0}}>
        {waves.map((w, i) => (
          <path
            key={`line-${i}`}
            d={wavePath(frame, w.base, w.amp * pulse, w.k, w.speed, w.phase)}
            stroke="#F43F5E"
            strokeWidth={w.width}
            strokeOpacity={w.opacity}
            fill="none"
          />
        ))}
      </svg>

      <AbsoluteFill
        style={{
          backgroundImage: 'repeating-linear-gradient(0deg, rgba(255,255,255,0.04) 0px, rgba(255,255,255,0.04) 2px, transparent 2px, transparent 7px)',
          backgroundPosition: `0px ${lineShift}px`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: scanBarY,
          height: 240,
          background: 'linear-gradient(180deg, transparent, rgba(225,29,72,0.13), transparent)',
        }}
      />

      <AbsoluteFill
        style={{
          margin: 26,
          border: `4px solid rgba(225,29,72,${framePulse})`,
          borderRadius: 6,
        }}
      />
      <Bracket corner="tl" />
      <Bracket corner="tr" />
      <Bracket corner="bl" />
      <Bracket corner="br" />

      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 52%, rgba(0,0,0,0.6) 100%)'}} />
    </AbsoluteFill>
  );
};
