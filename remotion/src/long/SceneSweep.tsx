import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {ACCENT} from './kit';

const LEN = 54; // frames the effect lasts at the start of a scene

/** Broadcast polish for explainer scenes: a soft light sweep crosses the frame and four thin corner brackets
 *  draw in and fade away. Sits above the scene content, never under the captions; no text. */
export const SceneSweep: React.FC = () => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  if (frame > LEN) return null;
  const p = frame / LEN;
  const x = interpolate(p, [0, 1], [-0.25, 1.15]) * width;
  const alpha = Math.sin(Math.PI * Math.min(1, p)) * 0.5;
  const draw = interpolate(frame, [0, 20], [0, 1], {extrapolateRight: 'clamp'});
  const fade = interpolate(frame, [30, LEN], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const m = 60, s = 90 * draw;
  const corner = (cx: number, cy: number, dx: number, dy: number) => (
    <path d={`M${cx} ${cy + dy * s} L${cx} ${cy} L${cx + dx * s} ${cy}`} stroke={ACCENT} strokeWidth={4} fill="none" strokeLinecap="round" />
  );
  return (
    <div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      <div style={{position: 'absolute', top: 0, bottom: 0, left: x - 160, width: 320, background: 'linear-gradient(100deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.9) 50%, rgba(255,255,255,0) 100%)', opacity: alpha * 0.22, transform: 'skewX(-14deg)'}} />
      <svg width={width} height={height} style={{position: 'absolute', left: 0, top: 0, opacity: fade * 0.9}}>
        {corner(m, 230, 1, 1)}
        {corner(width - m, 230, -1, 1)}
        {corner(m, height - 130, 1, -1)}
        {corner(width - m, height - 130, -1, -1)}
      </svg>
    </div>
  );
};
