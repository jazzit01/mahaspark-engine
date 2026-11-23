import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';

const BLOBS = [
  {x: 0.18, y: 0.30, r: 0.42, c: '#3b5bdb', sp: 0.11},
  {x: 0.80, y: 0.25, r: 0.36, c: '#0ea5a4', sp: 0.09},
  {x: 0.55, y: 0.85, r: 0.46, c: '#7c3aed', sp: 0.13},
  {x: 0.92, y: 0.80, r: 0.30, c: '#e8a33d', sp: 0.08},
];

/** "Aurora Flow": deep navy with slow colour glows and silky light ribbons (original SVG, no assets). */
export const AuroraStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const ribbon = (k: number, amp: number, phase: number) => {
    const pts: string[] = [];
    for (let i = 0; i <= 24; i++) {
      const x = (i / 24) * width;
      const y = height * (0.30 + 0.14 * k) + Math.sin(i * 0.42 + t * (0.35 + 0.08 * k) + phase) * amp + Math.sin(i * 0.17 - t * 0.2 + phase * 2) * amp * 0.6;
      pts.push(`${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    return pts.join(' ');
  };
  return (
    <AbsoluteFill style={{background: 'linear-gradient(160deg, #060b1d 0%, #0a1330 55%, #070d22 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <filter id="aur-blur"><feGaussianBlur stdDeviation="90" /></filter>
          <filter id="aur-soft"><feGaussianBlur stdDeviation="3" /></filter>
          <linearGradient id="aur-line" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#7dd3fc" stopOpacity="0" />
            <stop offset="0.5" stopColor="#c4b5fd" stopOpacity="0.9" />
            <stop offset="1" stopColor="#fcd34d" stopOpacity="0" />
          </linearGradient>
        </defs>
        {BLOBS.map((b, i) => (
          <circle key={i} cx={(b.x + Math.sin(t * b.sp + i * 2) * 0.07) * width} cy={(b.y + Math.cos(t * b.sp * 1.3 + i) * 0.07) * height} r={b.r * width * 0.5} fill={b.c} opacity={0.34} filter="url(#aur-blur)" />
        ))}
        {[0, 1, 2, 3, 4].map((k) => (
          <path key={k} d={ribbon(k, 46 + k * 9, k * 1.7)} stroke="url(#aur-line)" strokeWidth={2.2 + (k % 2)} fill="none" opacity={0.16 + 0.05 * (k % 3)} filter="url(#aur-soft)" />
        ))}
        {Array.from({length: 34}, (_, i) => (
          <circle key={`s${i}`} cx={random(`ax${i}`) * width} cy={((random(`ay${i}`) * height - t * (6 + random(`av${i}`) * 10) + height * 4) % height)} r={0.9 + random(`ar${i}`) * 2} fill="#e0e7ff" opacity={0.10 + 0.22 * Math.abs(Math.sin(t * 0.8 + i))} />
        ))}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
