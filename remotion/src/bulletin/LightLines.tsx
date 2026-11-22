import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS} from './constants';

const TRACE = '#6FA8FF';
const GLOW = '#FFD66B';

// circuit traces: 90 and 45 degree turns only, ending in pads
const TRACES = [
  'M0 160 L 380 160 L 470 250 L 900 250',
  'M0 420 L 220 420 L 300 500 L 300 700',
  'M1920 120 L 1500 120 L 1420 200 L 1420 420',
  'M560 0 L 560 90 L 640 170 L 1000 170',
  'M0 860 L 500 860 L 590 770 L 1100 770',
  'M1920 700 L 1560 700 L 1480 780 L 1480 1010',
];

/** Wind-like flow line: a sine ribbon with its own phase and speed. */
const flow = (i: number, t: number, w: number): string => {
  const y0 = 90 + i * 62;
  const amp = 26 + random(`fa${i}`) * 34;
  const ph = random(`fp${i}`) * 6.28 + t * (0.35 + random(`fs${i}`) * 0.3);
  let d = '';
  for (let x = 0; x <= w; x += 60) {
    const y = y0 + Math.sin(x / 260 + ph) * amp + Math.sin(x / 90 + ph * 1.7) * 7;
    d += `${x === 0 ? 'M' : 'L'}${x} ${y.toFixed(1)} `;
  }
  return d;
};

/**
 * "Light & Lines" bulletin background: the usual deep-blue gradient with circuit traces whose pulses run
 * along them, faint flow-field wind lines and drifting light points. Replaces the plain grid.
 */
export const LightLines: React.FC<{hue: number}> = ({hue}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const sx = width / 1920;
  const sy = height / 1080;
  return (
    <AbsoluteFill style={{background: `linear-gradient(160deg, ${COLORS.bgTop} 0%, ${COLORS.bgBottom} 100%)`, filter: hue ? `hue-rotate(${hue}deg)` : undefined}}>
      <AbsoluteFill style={{background: 'radial-gradient(900px 700px at 25% 40%, rgba(40,90,220,0.28), transparent 70%)'}} />
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5" /></filter>
        </defs>
        <g transform={`scale(${sx} ${sy})`}>
          {/* flow-field lines */}
          {Array.from({length: 14}, (_, i) => (
            <path key={`f${i}`} d={flow(i, t, 1920)} fill="none" stroke={TRACE} strokeOpacity={0.05 + (i % 3) * 0.02} strokeWidth={2} />
          ))}
          {/* circuit traces with a travelling pulse */}
          {TRACES.map((d, i) => {
            const pos = ((t * 0.16 + i * 0.37) % 1.4) - 0.2; // 0..1 along the path, with a pause off both ends
            const head = Math.min(1, Math.max(0, pos));
            const tail = Math.min(1, Math.max(0, pos - 0.14));
            const lit = head - tail;
            return (
              <g key={i}>
                <path d={d} pathLength={1} fill="none" stroke={TRACE} strokeOpacity={0.22} strokeWidth={3} strokeLinejoin="round" />
                {lit > 0 ? (
                  <>
                    <path d={d} pathLength={1} fill="none" stroke={GLOW} strokeWidth={9} strokeLinecap="round" strokeDasharray={`${lit} 2`} strokeDashoffset={-tail} opacity={0.5} filter="url(#glow)" />
                    <path d={d} pathLength={1} fill="none" stroke="#FFF3C9" strokeWidth={3.5} strokeLinecap="round" strokeDasharray={`${lit} 2`} strokeDashoffset={-tail} opacity={0.9} />
                  </>
                ) : null}
              </g>
            );
          })}
          {/* light points */}
          {Array.from({length: 22}, (_, i) => {
            const x = (random(`lx${i}`) * 1920 + Math.sin(t * 0.3 + i) * 40 + 1920) % 1920;
            const y = (random(`ly${i}`) * 1080 - t * (5 + random(`lv${i}`) * 9) + 1080 * 6) % 1080;
            const tw = 0.5 + 0.5 * Math.sin(t * (0.9 + random(`lt${i}`) * 1.4) + i);
            return <circle key={`p${i}`} cx={x} cy={y} r={2 + random(`lr${i}`) * 3} fill={GLOW} opacity={0.1 + tw * 0.4} filter={i % 3 === 0 ? 'url(#glow)' : undefined} />;
          })}
        </g>
      </svg>
    </AbsoluteFill>
  );
};
