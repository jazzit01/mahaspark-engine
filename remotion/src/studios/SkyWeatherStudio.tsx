import React from 'react';
import {AbsoluteFill, random, useCurrentFrame, useVideoConfig} from 'remotion';

/** Weather / environment / agriculture: dusk-blue sky, soft clouds drifting past and light rain. Original SVG. */
export const SkyWeatherStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #0B2447 0%, #19376D 52%, #2B5B93 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <filter id="sky-blur"><feGaussianBlur stdDeviation="38" /></filter>
        </defs>
        {Array.from({length: 9}, (_, i) => {
          const speed = 14 + random(`cs${i}`) * 22;
          const w = width * (0.5 + random(`cw${i}`) * 0.5);
          const x = ((random(`cx${i}`) * (width + w) + t * speed) % (width + w * 2)) - w;
          const y = height * (0.08 + random(`cy${i}`) * 0.62);
          return <ellipse key={i} cx={x} cy={y} rx={w / 2} ry={w * 0.13} fill="#DCE9FF" opacity={0.10 + random(`co${i}`) * 0.10} filter="url(#sky-blur)" />;
        })}
        {Array.from({length: 70}, (_, i) => {
          const x = random(`rx${i}`) * width;
          const y = ((random(`ry${i}`) * height + t * (700 + random(`rv${i}`) * 400)) % (height + 140)) - 70;
          return <line key={`r${i}`} x1={x} y1={y} x2={x - 14} y2={y + 52} stroke="#CFE0FF" strokeOpacity={0.12 + random(`ro${i}`) * 0.12} strokeWidth={2} strokeLinecap="round" />;
        })}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.45) 100%)'}} />
    </AbsoluteFill>
  );
};
