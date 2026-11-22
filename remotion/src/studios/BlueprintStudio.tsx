import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {DrawPath, cycleOpacity, drawn} from './lines';

const LINE = '#CFE8FF';
const ACCENT = '#7FD6FF';

const gearPath = (cx: number, cy: number, rOuter: number, rInner: number, teeth: number): string => {
  const pts: string[] = [];
  for (let i = 0; i < teeth; i++) {
    const a0 = (i / teeth) * Math.PI * 2;
    const a1 = a0 + (Math.PI * 2) / teeth;
    const q = (a: number, r: number) => `${(cx + Math.cos(a) * r).toFixed(1)},${(cy + Math.sin(a) * r).toFixed(1)}`;
    const w = a1 - a0;
    pts.push(`${i === 0 ? 'M' : 'L'}${q(a0, rInner)} L${q(a0 + w * 0.2, rOuter)} L${q(a0 + w * 0.5, rOuter)} L${q(a0 + w * 0.7, rInner)}`);
  }
  return pts.join(' ') + ' Z';
};

// an isometric cube wireframe, side 120 (drawn in a local box)
const CUBE = ['M0 -70 L 104 -10 L 104 110 L 0 170 L -104 110 L -104 -10 Z', 'M0 50 L 104 -10', 'M0 50 L -104 -10', 'M0 50 L 0 170', 'M0 -70 L 0 50'];

const dim = (x1: number, y: number, x2: number, label: string, p: number) => (
  <g opacity={0.5}>
    <DrawPath d={`M${x1} ${y} L${x2} ${y}`} progress={p} stroke={LINE} width={2} />
    <DrawPath d={`M${x1} ${y - 14} L${x1} ${y + 14} M${x2} ${y - 14} L${x2} ${y + 14}`} progress={p} stroke={LINE} width={2} />
    <DrawPath d={`M${x1 + 14} ${y - 7} L${x1} ${y} L${x1 + 14} ${y + 7} M${x2 - 14} ${y - 7} L${x2} ${y} L${x2 - 14} ${y + 7}`} progress={p} stroke={LINE} width={2} />
    <circle cx={(x1 + x2) / 2} cy={y} r={18} fill="#0b3a6b" stroke={LINE} strokeWidth={2} opacity={p} />
    <text x={(x1 + x2) / 2} y={y + 7} textAnchor="middle" fill={LINE} fontSize={20} fontFamily="monospace" opacity={p}>{label}</text>
  </g>
);

/** "Line Diagrams": blueprint paper with grid, slowly turning gears, an isometric wireframe and dimension lines that draw on. */
export const BlueprintStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const sx = width / 1920;
  const sy = height / 1080;
  const spin = t * 9;
  const loop = (period: number, offset: number) => cycleOpacity(t + offset, period, 0.8, 1.5);
  return (
    <AbsoluteFill style={{background: 'linear-gradient(160deg, #0d4380 0%, #0a3566 55%, #072a52 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        {/* paper grid: fine every 40, major every 200 */}
        {Array.from({length: Math.ceil(1920 / 40)}, (_, i) => (
          <line key={`v${i}`} x1={i * 40 * sx} x2={i * 40 * sx} y1={0} y2={height} stroke={LINE} strokeOpacity={i % 5 === 0 ? 0.13 : 0.05} strokeWidth={i % 5 === 0 ? 2 : 1} />
        ))}
        {Array.from({length: Math.ceil(1080 / 40)}, (_, i) => (
          <line key={`h${i}`} y1={i * 40 * sy} y2={i * 40 * sy} x1={0} x2={width} stroke={LINE} strokeOpacity={i % 5 === 0 ? 0.13 : 0.05} strokeWidth={i % 5 === 0 ? 2 : 1} />
        ))}
        {/* gear pair, bottom right (they mesh: opposite directions) */}
        <g transform={`translate(${1640 * sx} ${820 * sy}) scale(${sx})`} opacity={0.3}>
          <g transform={`rotate(${spin})`}>
            <path d={gearPath(0, 0, 150, 122, 16)} fill="none" stroke={LINE} strokeWidth={3} />
            <circle r={40} fill="none" stroke={LINE} strokeWidth={3} />
            <path d="M-150 0 L150 0 M0 -150 L0 150" stroke={LINE} strokeWidth={1.5} strokeDasharray="14 8 3 8" />
          </g>
          <g transform={`translate(215 -105) rotate(${-spin * 16 / 11 + 11})`}>
            <path d={gearPath(0, 0, 104, 82, 11)} fill="none" stroke={ACCENT} strokeWidth={3} />
            <circle r={26} fill="none" stroke={ACCENT} strokeWidth={3} />
          </g>
        </g>
        {/* isometric cube, top right, drawing on and off */}
        <g transform={`translate(${1530 * sx} ${230 * sy}) scale(${sx})`} opacity={0.34 * loop(16, 0)}>
          {CUBE.map((d, i) => <DrawPath key={i} d={d} progress={drawn((t + 0) % 16, 0.3 + i * 0.5, 1.6)} stroke={LINE} width={3} />)}
        </g>
        {/* concentric circle with centre lines, left bottom */}
        <g transform={`translate(${250 * sx} ${900 * sy}) scale(${sx})`} opacity={0.26 * loop(18, 6)}>
          {[40, 80, 120].map((r, i) => <DrawPath key={r} d={`M${-r} 0 a ${r} ${r} 0 1 0 ${2 * r} 0 a ${r} ${r} 0 1 0 ${-2 * r} 0`} progress={drawn((t + 6) % 18, 0.2 + i * 0.6, 1.8)} stroke={ACCENT} width={2.5} />)}
          <path d="M-150 0 L150 0 M0 -150 L0 150" stroke={LINE} strokeWidth={1.5} strokeDasharray="16 8 3 8" />
        </g>
        {/* dimension lines (animated, near the top and bottom edges) */}
        <g transform={`scale(${sx} ${sy})`}>
          {dim(1180, 120, 1760, '580', drawn((t + 2) % 14, 0.2, 1.8) * loop(14, 2))}
          {dim(120, 1010, 620, '500', drawn((t + 8) % 17, 0.2, 1.8) * loop(17, 8))}
        </g>
        {/* corner title block */}
        <g transform={`translate(${1520 * sx} ${960 * sy}) scale(${sx})`} opacity={0.22}>
          <rect width={340} height={80} fill="none" stroke={LINE} strokeWidth={2} />
          <path d="M0 40 L340 40 M200 0 L200 80" stroke={LINE} strokeWidth={1.5} />
        </g>
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(3,20,50,0) 50%, rgba(3,20,50,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
