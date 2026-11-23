import React from 'react';
import {AbsoluteFill, Audio, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ACCENT} from './kit';

export const STING_SECONDS = 1.35;

/** Signature opener over the first second of a long video: the logo punches in with a ring flash and a sound hit. */
export const Sting: React.FC<{silent?: boolean}> = ({silent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const total = STING_SECONDS * fps;
  if (frame > total) return null;
  const pop = spring({frame, fps, config: {damping: 11, stiffness: 160, mass: 0.7}});
  const fade = interpolate(frame, [total - 10, total], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const ring = interpolate(frame, [2, total * 0.8], [0.2, 2.4], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const flash = interpolate(frame, [0, 4, 14], [0, 0.55, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{opacity: fade, pointerEvents: 'none'}}>
      <AbsoluteFill style={{background: 'rgba(3,6,16,0.72)'}} />
      <AbsoluteFill style={{background: `rgba(255,255,255,${flash})`}} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{position: 'absolute', width: 420, height: 420, borderRadius: '50%', border: `8px solid ${ACCENT}`, opacity: 1 - Math.min(1, ring / 2.4), transform: `scale(${ring})`}} />
        <Img src={staticFile('logo.png')} style={{height: 330, transform: `scale(${0.55 + 0.45 * pop})`, opacity: Math.min(1, pop * 1.4), filter: 'drop-shadow(0 12px 40px rgba(0,0,0,0.6))'}} />
      </AbsoluteFill>
      {silent ? null : <Audio src={staticFile('sting.wav')} volume={0.55} />}
    </AbsoluteFill>
  );
};
