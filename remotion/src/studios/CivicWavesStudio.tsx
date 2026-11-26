import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

/** Politics / governance: deep indigo, a slow fan of gold light from the bottom and layered rolling waves. Original SVG. */
export const CivicWavesStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const wave = (k: number, color: string, opacity: number) => {
    const pts: string[] = [`M0 ${height}`];
    for (let i = 0; i <= 20; i++) {
      const x = (i / 20) * width;
      const y = height * (0.62 + 0.09 * k) + Math.sin(i * 0.55 + t * (0.28 + 0.07 * k) + k * 1.3) * (34 + 10 * k);
      pts.push(`L${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    pts.push(`L${width} ${height} Z`);
    return <path key={k} d={pts.join(' ')} fill={color} opacity={opacity} />;
  };
  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #0B1230 0%, #131C45 55%, #0A0F28 100%)'}}>
      <div
        style={{
          position: 'absolute',
          left: width / 2 - width * 0.9,
          top: height * 0.55,
          width: width * 1.8,
          height: width * 1.8,
          borderRadius: '50%',
          background: `conic-gradient(from ${-90 - 40 + Math.sin(t * 0.2) * 6}deg, rgba(232,163,61,0) 0deg, rgba(232,163,61,0.22) 40deg, rgba(232,163,61,0) 80deg)`,
          WebkitMaskImage: 'radial-gradient(circle, rgba(0,0,0,1) 15%, rgba(0,0,0,0) 62%)',
          maskImage: 'radial-gradient(circle, rgba(0,0,0,1) 15%, rgba(0,0,0,0) 62%)',
        }}
      />
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        {wave(0, '#E8A33D', 0.16)}
        {wave(1, '#F5F7FA', 0.10)}
        {wave(2, '#3B5BDB', 0.30)}
        {wave(3, '#0A0F28', 0.65)}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
