import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';

const NODES = 26;

/** "Knowledge Graph": a drifting network of nodes joined by thin lines, with light pulses running along them
 *  and slow orbit rings. Original SVG. */
export const OrbitStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const pos = (i: number) => ({
    x: (0.04 + 0.92 * random(`ox${i}`) + Math.sin(t * (0.10 + 0.05 * random(`os${i}`)) + i) * 0.025) * width,
    y: (0.06 + 0.88 * random(`oy${i}`) + Math.cos(t * (0.09 + 0.05 * random(`ot${i}`)) + i * 1.7) * 0.03) * height,
  });
  const nodes = Array.from({length: NODES}, (_, i) => pos(i));
  const edges: [number, number][] = [];
  nodes.forEach((a, i) => {
    nodes.forEach((b, j) => {
      if (j > i && Math.hypot(a.x - b.x, a.y - b.y) < width * 0.17) edges.push([i, j]);
    });
  });
  return (
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 30% 30%, #11224d 0%, #0a1531 55%, #060c1f 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <filter id="orb-glow"><feGaussianBlur stdDeviation="5" /></filter>
        </defs>
        {[0.16, 0.27, 0.40].map((r, i) => (
          <ellipse key={i} cx={width * 0.5} cy={height * 0.5} rx={width * r} ry={height * r * 0.9} fill="none" stroke="#7fb4ff" strokeOpacity={0.10} strokeWidth={2} strokeDasharray="4 14" transform={`rotate(${t * (3 + i * 1.5) * (i % 2 ? -1 : 1)} ${width * 0.5} ${height * 0.5})`} />
        ))}
        {edges.map(([a, b], k) => {
          const p = nodes[a], q = nodes[b];
          const along = ((t * 0.18 + random(`op${k}`)) % 1);
          return (
            <g key={k}>
              <line x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke="#8ab6ff" strokeOpacity={0.16} strokeWidth={1.6} />
              <circle cx={p.x + (q.x - p.x) * along} cy={p.y + (q.y - p.y) * along} r={3.2} fill="#ffd978" opacity={0.75} filter="url(#orb-glow)" />
            </g>
          );
        })}
        {nodes.map((n, i) => (
          <g key={i}>
            <circle cx={n.x} cy={n.y} r={9 + 5 * Math.abs(Math.sin(t * 0.6 + i))} fill="#4f8cff" opacity={0.16} />
            <circle cx={n.x} cy={n.y} r={i % 5 === 0 ? 5.5 : 3.6} fill={i % 5 === 0 ? '#ffd978' : '#cfe0ff'} opacity={0.85} />
          </g>
        ))}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 52%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
