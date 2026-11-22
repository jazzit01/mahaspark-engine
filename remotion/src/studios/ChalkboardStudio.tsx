import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {DrawPath, cycleOpacity, drawn} from './lines';

const CHALK = '#EAF1EC';
const PERIOD = 15; // seconds one doodle stays on the board before it is wiped and a new one is drawn

// doodles drawn in a 300 x 240 box, one stroke each (they draw themselves like chalk on slate)
const DOODLES: string[][] = [
  ['M20 200 C 80 40, 160 40, 200 120 S 260 200, 280 60', 'M262 82 L 282 54 L 292 92'], // curved arrow
  ['M150 40 C 90 40, 70 110, 110 150 C 125 165, 125 180, 125 195 L 175 195 C 175 180, 175 165, 190 150 C 230 110, 210 40, 150 40', 'M125 215 L 175 215', 'M140 235 L 160 235'], // bulb
  ['M150 30 L 183 110 L 270 116 L 203 170 L 226 255 L 150 205 L 74 255 L 97 170 L 30 116 L 117 110 Z'], // star
  ['M30 130 L 110 205 L 270 40'], // tick
  ['M20 160 C 60 100, 90 220, 130 150 S 190 100, 220 170 S 260 130, 285 150'], // squiggle
  ['M150 120 m -120 0 a 120 50 0 1 0 240 0 a 120 50 0 1 0 -240 0', 'M150 120 m -120 0 a 120 50 60 1 0 240 0 a 120 50 60 1 0 -240 0', 'M150 120 m -120 0 a 120 50 120 1 0 240 0 a 120 50 120 1 0 -240 0', 'M150 112 a 9 9 0 1 0 0.1 0'], // atom orbits
  ['M150 130 m 0 0 c 0 -14, 22 -14, 22 0 s -44 30, -44 0 s 66 -48, 66 0 s -88 66, -88 0 s 110 -84, 110 0'], // spiral
  ['M30 190 L 90 110 L 140 150 L 200 70 L 270 100', 'M30 215 L 270 215', 'M30 215 L 30 40'], // chart
];
// slots around the edge of the 1920x1080 board (the middle stays clear for the text)
const SLOTS = [
  {x: 1480, y: 90, s: 1.15}, {x: 1560, y: 770, s: 1.0}, {x: 30, y: 790, s: 0.95}, {x: 1290, y: 800, s: 0.9}, {x: 1600, y: 380, s: 0.9},
];

/** "Sketch & Board": slate chalkboard with a faint ruled grid, chalk dust and doodles that draw themselves. */
export const ChalkboardStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const sx = width / 1920;
  const sy = height / 1080;
  return (
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 40%, #1d2e28 0%, #13201b 60%, #0b1511 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <filter id="chalk" x="-5%" y="-5%" width="110%" height="110%">
            <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves={2} seed={4} result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale={3.2} />
          </filter>
          <filter id="smudge"><feGaussianBlur stdDeviation="26" /></filter>
        </defs>
        {/* wiped-chalk smudges */}
        {[0, 1, 2, 3].map((i) => (
          <ellipse key={i} cx={(250 + random(`sm${i}`) * 1400) * sx} cy={(150 + random(`sn${i}`) * 780) * sy} rx={(180 + random(`so${i}`) * 220) * sx} ry={(40 + random(`sp${i}`) * 60) * sy} fill="#f4f8f5" opacity={0.035} transform={`rotate(${-20 + random(`sr${i}`) * 40} ${900 * sx} ${540 * sy})`} filter="url(#smudge)" />
        ))}
        {/* faint ruled grid */}
        {Array.from({length: 11}, (_, i) => (
          <line key={`h${i}`} x1={0} x2={width} y1={(i + 1) * 90 * sy} y2={(i + 1) * 90 * sy} stroke={CHALK} strokeOpacity={0.045} strokeWidth={2} />
        ))}
        <line x1={150 * sx} x2={150 * sx} y1={0} y2={height} stroke="#F28B82" strokeOpacity={0.10} strokeWidth={3} />
        {/* doodles */}
        {SLOTS.map((slot, i) => {
          const phase = t + i * 3.1;
          const cycle = Math.floor(phase / PERIOD);
          const strokes = DOODLES[Math.floor(random(`d${i}-${cycle}`) * DOODLES.length)];
          const local = phase - cycle * PERIOD;
          const alpha = 0.34 * cycleOpacity(local, PERIOD, 0.2, 1.8);
          return (
            <g key={i} transform={`translate(${slot.x * sx} ${slot.y * sy}) scale(${slot.s * sx})`} filter="url(#chalk)">
              {strokes.map((d, k) => (
                <DrawPath key={k} d={d} progress={drawn(local, 0.3 + k * 1.2, 2.2)} stroke={CHALK} width={4.5} opacity={alpha} />
              ))}
            </g>
          );
        })}
        {/* chalk dust */}
        {Array.from({length: 26}, (_, i) => (
          <circle key={`d${i}`} cx={((random(`dx${i}`) * 1920 + t * (4 + random(`dv${i}`) * 8)) % 1920) * sx} cy={((random(`dy${i}`) * 1080 - t * (3 + random(`dw${i}`) * 6) + 1080 * 4) % 1080) * sy} r={1.2 + random(`dr${i}`) * 2.4} fill={CHALK} opacity={0.08 + random(`do${i}`) * 0.14} />
        ))}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)'}} />
    </AbsoluteFill>
  );
};
