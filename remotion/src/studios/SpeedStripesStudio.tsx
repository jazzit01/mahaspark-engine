import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

/** Sports: night-stadium dark, diagonal speed stripes sliding across, floodlight glows in the top corners and lane
 *  lines running toward the viewer. Original SVG. */
export const SpeedStripesStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const stripe = (i: number, layer: number) => {
    const speed = 160 + layer * 140;
    const span = width + height;
    const x = ((i * span) / 9 + t * speed) % span - height * 0.5;
    const w = 40 + layer * 46;
    return (
      <polygon
        key={`${layer}-${i}`}
        points={`${x},${height} ${x + w},${height} ${x + w + height * 0.5},0 ${x + height * 0.5},0`}
        fill={layer === 0 ? '#F97316' : '#22D3EE'}
        opacity={layer === 0 ? 0.10 : 0.07}
      />
    );
  };
  const lanes = Array.from({length: 7}, (_, i) => {
    const fx = (i - 3) * width * 0.34 + width / 2;
    const phase = (t * 0.6 + i * 0.1) % 1;
    return <line key={i} x1={width / 2 + (fx - width / 2) * 0.1} y1={height * 0.58} x2={fx} y2={height} stroke="#FFFFFF" strokeOpacity={0.07 + 0.06 * phase} strokeWidth={3} />;
  });
  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #0A1020 0%, #0E1730 60%, #070B16 100%)'}}>
      <div style={{position: 'absolute', left: -width * 0.2, top: -height * 0.12, width: width * 0.9, height: width * 0.9, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,244,214,0.30) 0%, rgba(255,244,214,0) 65%)'}} />
      <div style={{position: 'absolute', right: -width * 0.2, top: -height * 0.10, width: width * 0.9, height: width * 0.9, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,244,214,0.24) 0%, rgba(255,244,214,0) 65%)'}} />
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        {[0, 1].flatMap((layer) => Array.from({length: 9}, (_, i) => stripe(i, layer)))}
        {lanes}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
