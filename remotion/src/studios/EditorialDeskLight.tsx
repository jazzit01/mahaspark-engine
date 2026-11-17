import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

const INK = '#0F172A';
const RED = '#D90429';

/** Crisp ivory studio with drifting geometric framing lines and broadcast-red accent bars. */
export const EditorialDeskLight: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width: WIDTH, height: HEIGHT} = useVideoConfig();
  const t = frame / fps;

  const draw = interpolate(frame, [0, 30], [0, 1], {extrapolateRight: 'clamp'});
  const dashDrift = -frame * 0.7;
  const diagShift = (t * 26) % 260;
  const ring = (t * 6) % 360;

  const diagonals = Array.from({length: 9}, (_, i) => -600 + i * 260);

  return (
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 30%, #FFFFFF 0%, #F8FAFC 55%, #EEF2F7 100%)'}}>
      <svg width={WIDTH} height={HEIGHT} style={{position: 'absolute', left: 0, top: 0}}>
        <g transform={`translate(${diagShift} 0)`}>
          {diagonals.map((x) => (
            <line key={x} x1={x} y1={0} x2={x + 900} y2={HEIGHT} stroke={INK} strokeOpacity={0.055} strokeWidth={2} />
          ))}
        </g>

        <rect
          x={40}
          y={40}
          width={WIDTH - 80}
          height={HEIGHT - 80}
          fill="none"
          stroke={INK}
          strokeOpacity={0.14}
          strokeWidth={2}
          strokeDasharray="18 14"
          strokeDashoffset={dashDrift}
          pathLength={1}
          style={{opacity: draw}}
        />
        <rect x={76} y={76} width={WIDTH - 152} height={HEIGHT - 152} fill="none" stroke={INK} strokeOpacity={0.07} strokeWidth={2} />

        <circle cx={540} cy={1130} r={430} fill="none" stroke={INK} strokeOpacity={0.07} strokeWidth={2} />
        <g transform={`rotate(${ring} 540 1130)`}>
          <circle cx={540} cy={1130} r={540} fill="none" stroke={INK} strokeOpacity={0.12} strokeWidth={2} strokeDasharray="6 26" />
          <circle cx={540 + 540} cy={1130} r={9} fill={RED} fillOpacity={0.85} />
        </g>
      </svg>

      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 330 + 26 * Math.sin(t * 0.8),
          width: 20,
          height: 250,
          background: RED,
        }}
      />
      <div
        style={{
          position: 'absolute',
          right: 0,
          top: 1180 - 26 * Math.sin(t * 0.8),
          width: 20,
          height: 190,
          background: RED,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 60,
          bottom: 150,
          height: 12,
          width: (240 + 60 * Math.sin(t * 1.1)) * draw,
          background: RED,
        }}
      />
      <div style={{position: 'absolute', left: 60, bottom: 150, width: 960, height: 2, background: INK, opacity: 0.12 * draw}} />
    </AbsoluteFill>
  );
};
