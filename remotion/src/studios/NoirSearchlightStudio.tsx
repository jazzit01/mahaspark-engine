import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';

/** Crime / courts: charcoal, two slow searchlight beams, faint rain streaks and a soft, slow red/blue glow at the
 *  edges (a gentle 3 s fade, never a flash). Original SVG. */
export const NoirSearchlightStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const beam = (originX: number, base: number, sway: number) => {
    const angle = ((base + Math.sin(t * 0.35 + sway) * 14) * Math.PI) / 180;
    const len = height * 1.3;
    const spread = 0.11;
    const a = [originX + Math.sin(angle - spread) * len, height - Math.cos(angle - spread) * len];
    const b = [originX + Math.sin(angle + spread) * len, height - Math.cos(angle + spread) * len];
    return <polygon points={`${originX},${height} ${a[0]},${a[1]} ${b[0]},${b[1]}`} fill="url(#noir-beam)" opacity={0.55} />;
  };
  const red = 0.10 + 0.08 * Math.sin((t * Math.PI * 2) / 3);
  const blue = 0.10 + 0.08 * Math.sin((t * Math.PI * 2) / 3 + Math.PI);
  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #0B0D12 0%, #10131B 60%, #07080C 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <linearGradient id="noir-beam" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0" stopColor="#DCE7FF" stopOpacity="0.30" />
            <stop offset="1" stopColor="#DCE7FF" stopOpacity="0" />
          </linearGradient>
          <filter id="noir-blur"><feGaussianBlur stdDeviation="120" /></filter>
        </defs>
        <circle cx={0} cy={height * 0.18} r={width * 0.6} fill="#D90429" opacity={red} filter="url(#noir-blur)" />
        <circle cx={width} cy={height * 0.22} r={width * 0.6} fill="#2563EB" opacity={blue} filter="url(#noir-blur)" />
        {beam(width * 0.15, 18, 0)}
        {beam(width * 0.85, -20, 2)}
        {Array.from({length: 46}, (_, i) => {
          const x = random(`nx${i}`) * width;
          const y = ((random(`ny${i}`) * height + t * (420 + random(`nv${i}`) * 260)) % (height + 120)) - 60;
          return <line key={i} x1={x} y1={y} x2={x - 9} y2={y + 46} stroke="#9FB2D6" strokeOpacity={0.10 + random(`no${i}`) * 0.10} strokeWidth={1.6} />;
        })}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,0.65) 100%)'}} />
    </AbsoluteFill>
  );
};
