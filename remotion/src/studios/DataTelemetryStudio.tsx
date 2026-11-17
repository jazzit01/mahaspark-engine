import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';

const EMERALD = '#10B981';
const GOLD = '#FBBF24';
const CX = 540;
const CY = 900;
const NODE_COUNT = 16;

type Node = {x: number; y: number};

/** Midnight blue studio: rotating radar rings and sweep, floating telemetry nodes, emerald/gold metric callouts. */
export const DataTelemetryStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width: WIDTH, height: HEIGHT} = useVideoConfig();
  const t = frame / fps;

  const sweep = (t * 55) % 360;
  const rings = [170, 300, 430, 560, 700];

  const nodes: Node[] = Array.from({length: NODE_COUNT}, (_, i) => {
    const bx = 90 + random(`nx-${i}`) * (WIDTH - 180);
    const by = 330 + random(`ny-${i}`) * (HEIGHT - 800);
    const sp = 0.25 + random(`ns-${i}`) * 0.5;
    const ph = random(`np-${i}`) * Math.PI * 2;
    return {x: bx + Math.sin(t * sp + ph) * 34, y: by + Math.cos(t * sp * 0.8 + ph) * 28};
  });

  const links: Array<[Node, Node]> = [];
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
      if (d < 330) links.push([nodes[i], nodes[j]]);
    }
  }

  const bars = Array.from({length: 14}, (_, i) => 36 + 96 * Math.abs(Math.sin(t * 1.35 + i * 0.62)));
  const gauge = 0.55 + 0.35 * Math.sin(t * 0.9);
  const gaugeLength = 2 * Math.PI * 62;

  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #0A1636 0%, #050B1F 55%, #030717 100%)'}}>
      <div
        style={{
          position: 'absolute',
          left: CX - 700,
          top: CY - 700,
          width: 1400,
          height: 1400,
          borderRadius: '50%',
          background: `conic-gradient(from ${sweep}deg, rgba(16,185,129,0) 0deg, rgba(16,185,129,0.30) 52deg, rgba(16,185,129,0) 53deg)`,
          WebkitMaskImage: 'radial-gradient(circle, rgba(0,0,0,1) 25%, rgba(0,0,0,0) 70%)',
          maskImage: 'radial-gradient(circle, rgba(0,0,0,1) 25%, rgba(0,0,0,0) 70%)',
        }}
      />

      <svg width={WIDTH} height={HEIGHT} style={{position: 'absolute', left: 0, top: 0}}>
        <line x1={CX} y1={CY - 760} x2={CX} y2={CY + 760} stroke={EMERALD} strokeOpacity={0.14} strokeWidth={2} />
        <line x1={CX - 760} y1={CY} x2={CX + 760} y2={CY} stroke={EMERALD} strokeOpacity={0.14} strokeWidth={2} />

        {rings.map((r, i) => (
          <g key={r} transform={`rotate(${(i % 2 === 0 ? 1 : -1) * t * (6 + i * 3)} ${CX} ${CY})`}>
            <circle
              cx={CX}
              cy={CY}
              r={r}
              fill="none"
              stroke={i === 2 ? GOLD : EMERALD}
              strokeOpacity={i === 2 ? 0.3 : 0.26}
              strokeWidth={i % 2 === 0 ? 2 : 3}
              strokeDasharray={i % 2 === 0 ? '4 18' : '70 40'}
            />
            <circle cx={CX + r} cy={CY} r={7} fill={i === 2 ? GOLD : EMERALD} fillOpacity={0.9} />
          </g>
        ))}

        {links.map(([a, b], i) => (
          <line key={`l-${i}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={EMERALD} strokeOpacity={0.14} strokeWidth={1.5} />
        ))}
        {nodes.map((n, i) => {
          const pulse = (t * 0.8 + i * 0.37) % 1;
          return (
            <g key={`n-${i}`}>
              <circle cx={n.x} cy={n.y} r={5 + pulse * 20} fill="none" stroke={i % 3 === 0 ? GOLD : EMERALD} strokeOpacity={0.4 * (1 - pulse)} strokeWidth={2} />
              <circle cx={n.x} cy={n.y} r={5} fill={i % 3 === 0 ? GOLD : EMERALD} fillOpacity={0.9} />
            </g>
          );
        })}

        <circle cx={900} cy={1700} r={62} fill="none" stroke={EMERALD} strokeOpacity={0.2} strokeWidth={10} />
        <circle
          cx={900}
          cy={1700}
          r={62}
          fill="none"
          stroke={GOLD}
          strokeWidth={10}
          strokeLinecap="round"
          strokeDasharray={`${gaugeLength * gauge} ${gaugeLength}`}
          transform="rotate(-90 900 1700)"
        />
      </svg>

      <div style={{position: 'absolute', left: 70, bottom: 150, display: 'flex', alignItems: 'flex-end', gap: 10, height: 140}}>
        {bars.map((h, i) => (
          <div key={i} style={{width: 14, height: h, background: i % 4 === 3 ? GOLD : EMERALD, opacity: 0.85}} />
        ))}
      </div>

      <div style={{position: 'absolute', right: 60, top: 262, width: 90, height: 90, borderTop: `6px solid ${GOLD}`, borderRight: `6px solid ${GOLD}`}} />
      <div style={{position: 'absolute', left: 60, top: 262, width: 90, height: 90, borderTop: `6px solid ${EMERALD}`, borderLeft: `6px solid ${EMERALD}`}} />

      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.55) 100%)'}} />
    </AbsoluteFill>
  );
};
