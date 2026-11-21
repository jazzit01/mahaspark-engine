import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS} from '../bulletin/constants';
import {useReveal} from './kit';
import {GeoPin} from './types';

/** Simplified (schematic) outline of Maharashtra as [lat, lon] points, clockwise from the north-west coast. */
export const MAHARASHTRA_OUTLINE: [number, number][] = [
  [20.1, 72.75], [20.6, 73.05], [21.1, 73.4], [21.6, 73.75], [21.9, 74.1], [21.6, 75.0], [21.4, 76.0], [21.6, 76.8],
  [21.7, 77.8], [21.5, 78.4], [21.9, 78.6], [21.7, 79.2], [21.5, 79.9], [21.6, 80.5], [21.2, 80.6], [20.4, 80.4],
  [19.9, 80.8], [19.4, 80.9], [18.9, 80.2], [18.5, 80.0], [19.0, 79.5], [19.6, 79.1], [19.9, 78.5], [19.3, 78.2],
  [19.0, 77.9], [18.6, 77.8], [18.4, 77.3], [18.0, 77.6], [17.9, 76.8], [17.2, 76.3], [16.9, 75.7], [16.7, 74.8],
  [16.3, 74.4], [15.9, 74.2], [15.7, 73.85], [16.0, 73.65], [17.0, 73.3], [18.0, 73.0], [18.9, 72.85], [19.5, 72.75],
];

/** A few well-known cities for orientation (drawn small and dim). */
const LANDMARKS: {name: string; lat: number; lon: number}[] = [
  {name: 'मुंबई', lat: 18.97, lon: 72.82},
  {name: 'पुणे', lat: 18.52, lon: 73.86},
  {name: 'नागपूर', lat: 21.15, lon: 79.09},
];

const LAT_MIN = 15.4;
const LAT_MAX = 22.3;
const LON_MIN = 72.4;
const LON_MAX = 81.2;
const K = Math.cos((19 * Math.PI) / 180); // equirectangular, corrected for latitude

export const MAP_W = 640;
export const MAP_H = Math.round(((LAT_MAX - LAT_MIN) / ((LON_MAX - LON_MIN) * K)) * MAP_W);

export const project = (lat: number, lon: number): [number, number] => [
  ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * MAP_W,
  ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * MAP_H,
];

const outlinePath = (): string =>
  MAHARASHTRA_OUTLINE.map(([lat, lon], i) => {
    const [x, y] = project(lat, lon);
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ') + ' Z';

/** The state outline draws itself, then the pin drops with a pulsing ring and its label. */
export const GeoMap: React.FC<{pin: GeoPin; scale?: number; delaySeconds?: number}> = ({pin, scale = 1, delaySeconds = 0.2}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const draw = Math.min(1, Math.max(0, (t - delaySeconds) / 1.3));
  const fill = useReveal(delaySeconds + 1.0);
  const drop = useReveal(delaySeconds + 1.2, 12);
  const [px, py] = project(pin.lat, pin.lon);
  const pulse = (t * 1.1) % 1;
  const labelRight = px < MAP_W * 0.55;
  return (
    <div style={{position: 'relative', width: MAP_W * scale, height: MAP_H * scale, fontFamily}}>
      <svg viewBox={`0 0 ${MAP_W} ${MAP_H}`} width={MAP_W * scale} height={MAP_H * scale} style={{overflow: 'visible'}}>
        <defs>
          <filter id="mapglow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <path d={outlinePath()} fill={`rgba(245,196,81,${0.1 * fill})`} stroke={COLORS.gold} strokeWidth={4} strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} filter="url(#mapglow)" />
        {LANDMARKS.map((c) => {
          const [x, y] = project(c.lat, c.lon);
          return (
            <g key={c.name} opacity={0.65 * fill}>
              <circle cx={x} cy={y} r={5} fill="#F8FAFC" />
              <text x={x + 12} y={y + 8} fill="#F8FAFC" fontSize={24} fontWeight={600}>{c.name}</text>
            </g>
          );
        })}
        <g opacity={drop} transform={`translate(0 ${(1 - drop) * -40})`}>
          <circle cx={px} cy={py} r={14 + 46 * pulse} fill="none" stroke={COLORS.red} strokeWidth={4} opacity={1 - pulse} />
          <circle cx={px} cy={py} r={13} fill={COLORS.red} stroke="#fff" strokeWidth={4} />
          <text x={labelRight ? px + 26 : px - 26} y={py - 18} textAnchor={labelRight ? 'start' : 'end'} fill="#fff" fontSize={40} fontWeight={800} stroke="rgba(8,14,26,0.85)" strokeWidth={8} paintOrder="stroke">{pin.label}</text>
        </g>
      </svg>
    </div>
  );
};
