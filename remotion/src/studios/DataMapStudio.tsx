import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {DrawPath, drawn} from './lines';

const INK = '#E8F4F1';
const LINES = ['#35D0BA', '#FFB347', '#FF6F91', '#7AA8FF'];

// transit-style routes on a 1920x1080 plane: horizontal, vertical and 45-degree segments only
const ROUTES: {d: string; stops: [number, number][]}[] = [
  {d: 'M0 880 L 420 880 L 560 740 L 1180 740 L 1320 880 L 1920 880', stops: [[420, 880], [860, 740], [1320, 880], [1700, 880]]},
  {d: 'M200 0 L 200 260 L 340 400 L 340 620 L 120 840 L 120 1080', stops: [[200, 260], [340, 520], [120, 840]]},
  {d: 'M1920 220 L 1500 220 L 1360 360 L 1360 520 L 1500 660 L 1920 660', stops: [[1500, 220], [1360, 440], [1500, 660], [1780, 660]]},
  {d: 'M700 0 L 700 120 L 820 240 L 1260 240 L 1380 120 L 1380 0', stops: [[820, 240], [1260, 240]]},
];

/** Contour rings around one centre, drawn as hand-sized irregular ellipses. */
const Contours: React.FC<{cx: number; cy: number; rings: number; seed: string; t: number}> = ({cx, cy, rings, seed, t}) => (
  <g transform={`translate(${cx} ${cy})`}>
    {Array.from({length: rings}, (_, i) => {
      const r = 60 + i * 52;
      const wob = 0.88 + random(`${seed}${i}`) * 0.24;
      return <ellipse key={i} rx={r * 1.25 * wob} ry={r * 0.8} fill="none" stroke={INK} strokeOpacity={0.07 + (i % 4 === 0 ? 0.06 : 0)} strokeWidth={i % 4 === 0 ? 2.5 : 1.5} transform={`rotate(${-18 + i * 3 + Math.sin(t / 6 + i) * 1.2})`} />;
    })}
  </g>
);

/** "Data & Maps": dark slate map with contour lines, a faint lat/long graticule and transit-style routes with stations that draw on. */
export const DataMapStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const sx = width / 1920;
  const sy = height / 1080;
  return (
    <AbsoluteFill style={{background: 'linear-gradient(170deg, #0e1c26 0%, #0a1620 60%, #07111a 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <g transform={`scale(${sx} ${sy})`}>
          <Contours cx={1450} cy={470} rings={9} seed="a" t={t} />
          <Contours cx={430} cy={560} rings={7} seed="b" t={t} />
          {/* graticule */}
          {Array.from({length: 9}, (_, i) => (
            <line key={`v${i}`} x1={i * 240} x2={i * 240 + 70} y1={0} y2={1080} stroke={INK} strokeOpacity={0.045} strokeWidth={1.5} />
          ))}
          {Array.from({length: 6}, (_, i) => (
            <path key={`h${i}`} d={`M0 ${i * 216 + 40} Q 960 ${i * 216 - 10} 1920 ${i * 216 + 40}`} fill="none" stroke={INK} strokeOpacity={0.045} strokeWidth={1.5} />
          ))}
          {/* routes */}
          {ROUTES.map((r, i) => {
            const color = LINES[i % LINES.length];
            const p = drawn(t, 0.4 + i * 0.9, 3.2);
            return (
              <g key={i} opacity={0.5}>
                <DrawPath d={r.d} progress={p} stroke={color} width={11} />
                {r.stops.map(([x, y], k) => {
                  const on = p > (k + 1) / (r.stops.length + 1) ? 1 : 0;
                  const pulse = 1 + 0.25 * Math.sin(t * 2.4 + k + i);
                  return (
                    <g key={k} opacity={on}>
                      <circle cx={x} cy={y} r={16} fill="#0a1620" stroke={INK} strokeWidth={4} />
                      <circle cx={x} cy={y} r={30 * pulse} fill="none" stroke={color} strokeOpacity={0.35} strokeWidth={2} />
                    </g>
                  );
                })}
              </g>
            );
          })}
          {/* data points drifting along the first route */}
          {Array.from({length: 18}, (_, i) => (
            <circle key={i} cx={random(`px${i}`) * 1920} cy={random(`py${i}`) * 1080} r={3 + random(`pr${i}`) * 4} fill={LINES[i % LINES.length]} opacity={0.12 + 0.18 * (0.5 + 0.5 * Math.sin(t * 1.3 + i * 1.7))} />
          ))}
        </g>
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 52%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
