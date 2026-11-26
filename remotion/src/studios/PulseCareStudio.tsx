import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

/** Health / welfare: deep teal with soft green ripples and a heartbeat line that keeps travelling. Original SVG. */
export const PulseCareStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const beat = 520; // px per heartbeat
  const base = height * 0.5;
  const pts: string[] = [];
  for (let x = 0; x <= width + 4; x += 4) {
    const u = (((x + t * 260) % beat) + beat) % beat / beat;
    let y = 0;
    if (u > 0.10 && u < 0.18) y = -Math.sin(((u - 0.10) / 0.08) * Math.PI) * 26;
    else if (u > 0.30 && u < 0.34) y = ((u - 0.30) / 0.04) * 30;
    else if (u >= 0.34 && u < 0.40) y = 30 - ((u - 0.34) / 0.06) * 190;
    else if (u >= 0.40 && u < 0.46) y = -160 + ((u - 0.40) / 0.06) * 210;
    else if (u >= 0.46 && u < 0.50) y = 50 - ((u - 0.46) / 0.04) * 50;
    else if (u > 0.60 && u < 0.74) y = -Math.sin(((u - 0.60) / 0.14) * Math.PI) * 40;
    pts.push(`${x === 0 ? 'M' : 'L'}${x} ${(base + y).toFixed(1)}`);
  }
  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #06181C 0%, #0A2A30 55%, #051418 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        {[0, 1, 2, 3].map((i) => {
          const p = ((t * 0.18 + i / 4) % 1);
          return <circle key={i} cx={width / 2} cy={base} r={p * width * 0.75} fill="none" stroke="#34D399" strokeOpacity={0.22 * (1 - p)} strokeWidth={3} />;
        })}
        <path d={pts.join(' ')} stroke="#34D399" strokeOpacity={0.25} strokeWidth={14} fill="none" strokeLinejoin="round" />
        <path d={pts.join(' ')} stroke="#A7F3D0" strokeOpacity={0.85} strokeWidth={4} fill="none" strokeLinejoin="round" />
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
