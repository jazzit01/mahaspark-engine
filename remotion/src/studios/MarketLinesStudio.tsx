import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

/** Business / markets / economy: near-black blue with a faint grid, a gold trend line that keeps scrolling and a row of
 *  candlesticks along the bottom. Original SVG, no real market data. */
export const MarketLinesStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const N = 40;
  const series = (offset: number, amp: number) =>
    Array.from({length: N + 1}, (_, i) => {
      const x = (i / N) * width;
      const k = i + t * 2.2;
      const y = height * (0.5 - 0.0035 * ((k + offset) % 60)) + Math.sin(k * 0.55 + offset) * amp + Math.sin(k * 0.21) * amp * 1.6;
      return [x, y] as const;
    });
  const gold = series(0, 22);
  const cyan = series(17, 30);
  const path = (pts: ReadonlyArray<readonly [number, number]>) => pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const goldPath = path(gold);
  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #07121F 0%, #0B1B30 60%, #050C16 100%)'}}>
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0}}>
        <defs>
          <linearGradient id="mkt-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#FBBF24" stopOpacity="0.22" />
            <stop offset="1" stopColor="#FBBF24" stopOpacity="0" />
          </linearGradient>
        </defs>
        {Array.from({length: 9}, (_, i) => (
          <line key={`h${i}`} x1={0} x2={width} y1={(i / 8) * height} y2={(i / 8) * height} stroke="#7FB4FF" strokeOpacity={0.07} strokeWidth={1.5} />
        ))}
        {Array.from({length: 7}, (_, i) => (
          <line key={`v${i}`} y1={0} y2={height} x1={(i / 6) * width} x2={(i / 6) * width} stroke="#7FB4FF" strokeOpacity={0.05} strokeWidth={1.5} />
        ))}
        <path d={`${goldPath} L${width} ${height} L0 ${height} Z`} fill="url(#mkt-area)" />
        <path d={path(cyan)} stroke="#22D3EE" strokeOpacity={0.35} strokeWidth={3} fill="none" />
        <path d={goldPath} stroke="#FBBF24" strokeOpacity={0.8} strokeWidth={4} fill="none" strokeLinejoin="round" />
        {Array.from({length: 22}, (_, i) => {
          const k = i + Math.floor(t * 1.5);
          const up = Math.sin(k * 1.7) > -0.2;
          const x = ((i - ((t * 1.5) % 1)) / 21) * width;
          const body = 30 + Math.abs(Math.sin(k * 2.3)) * 90;
          const base = height * 0.9 - Math.abs(Math.sin(k * 0.9)) * 120;
          return (
            <g key={`c${i}`} opacity={0.30}>
              <line x1={x} x2={x} y1={base - body - 26} y2={base + 26} stroke={up ? '#34D399' : '#F87171'} strokeWidth={3} />
              <rect x={x - 10} y={base - body} width={20} height={body} fill={up ? '#34D399' : '#F87171'} />
            </g>
          );
        })}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.5) 100%)'}} />
    </AbsoluteFill>
  );
};
