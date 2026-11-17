import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

type Blob = {color: string; size: number; cx: number; cy: number; ax: number; ay: number; fx: number; fy: number; phase: number};

const BLOBS: Blob[] = [
  {color: 'rgba(99,102,241,0.62)', size: 1100, cx: 260, cy: 520, ax: 150, ay: 120, fx: 0.11, fy: 0.07, phase: 0},
  {color: 'rgba(56,189,248,0.40)', size: 900, cx: 860, cy: 980, ax: 170, ay: 150, fx: 0.08, fy: 0.12, phase: 1.9},
  {color: 'rgba(139,92,246,0.50)', size: 1000, cx: 300, cy: 1500, ax: 140, ay: 130, fx: 0.1, fy: 0.09, phase: 3.4},
  {color: 'rgba(251,191,36,0.20)', size: 700, cx: 820, cy: 1650, ax: 120, ay: 100, fx: 0.13, fy: 0.08, phase: 5.0},
];

const mesh = (frame: number, fps: number, WIDTH: number, HEIGHT: number) => {
  const t = frame / fps;
  const horizontal: string[] = [];
  for (let row = 0; row < 11; row++) {
    const base = 120 + row * 170;
    let d = '';
    for (let x = 0; x <= WIDTH; x += 30) {
      const y = base + 26 * Math.sin(x * 0.007 + t * 0.5 + row * 0.6);
      d += `${x === 0 ? 'M' : 'L'}${x},${y.toFixed(1)} `;
    }
    horizontal.push(d);
  }
  const vertical: string[] = [];
  for (let col = 0; col < 8; col++) {
    const base = 60 + col * 140;
    let d = '';
    for (let y = 0; y <= HEIGHT; y += 40) {
      const x = base + 22 * Math.sin(y * 0.005 + t * 0.45 + col * 0.8);
      d += `${y === 0 ? 'M' : 'L'}${x.toFixed(1)},${y} `;
    }
    vertical.push(d);
  }
  return {horizontal, vertical};
};

/** Deep indigo-slate depth with slow volumetric light and a drifting light mesh behind frosted-glass cards. */
export const GlassNewsroomDepth: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width: WIDTH, height: HEIGHT} = useVideoConfig();
  const t = frame / fps;
  const {horizontal, vertical} = mesh(frame, fps, WIDTH, HEIGHT);

  const beamOpacity = 0.5 + 0.5 * Math.sin(t * 0.35);

  return (
    <AbsoluteFill style={{background: 'linear-gradient(160deg, #151A3F 0%, #0E1230 50%, #0A0D26 100%)'}}>
      {BLOBS.map((b, i) => {
        const x = b.cx + b.ax * Math.sin(t * b.fx * Math.PI * 2 + b.phase);
        const y = b.cy + b.ay * Math.cos(t * b.fy * Math.PI * 2 + b.phase);
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x - b.size / 2,
              top: y - b.size / 2,
              width: b.size,
              height: b.size,
              borderRadius: '50%',
              background: `radial-gradient(circle, ${b.color} 0%, rgba(0,0,0,0) 66%)`,
            }}
          />
        );
      })}

      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            top: -200,
            left: 140 + i * 340 + 70 * Math.sin(t * 0.22 + i * 1.7),
            width: 170,
            height: 2300,
            transform: 'rotate(14deg)',
            background: 'linear-gradient(180deg, rgba(190,210,255,0.16), rgba(190,210,255,0))',
            opacity: 0.35 + 0.35 * Math.abs(Math.sin(t * 0.35 + i)) * beamOpacity,
            mixBlendMode: 'screen',
          }}
        />
      ))}

      <svg width={WIDTH} height={HEIGHT} style={{position: 'absolute', left: 0, top: 0}}>
        {horizontal.map((d, i) => (
          <path key={`h-${i}`} d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.055} strokeWidth={1.5} />
        ))}
        {vertical.map((d, i) => (
          <path key={`v-${i}`} d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.04} strokeWidth={1.5} />
        ))}
      </svg>

      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 52%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
