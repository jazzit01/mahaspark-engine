import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {CHANNEL_HANDLE, COLORS} from './constants';

/** The one fixed outro, identical in every bulletin: logo, follow call, animated subscribe pill, channel handle. */
export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = (delay: number) => spring({frame: frame - delay, fps, config: {damping: 12, mass: 0.8}});
  const rise = (delay: number) => spring({frame: frame - delay, fps, config: {damping: 200}});
  const pulse = 1 + Math.sin(frame / 6) * 0.03;
  const tap = interpolate(frame % 60, [0, 10, 20], [1, 0.94, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: `linear-gradient(160deg, ${COLORS.bgTop} 0%, ${COLORS.bgBottom} 100%)`, alignItems: 'center', justifyContent: 'center', fontFamily}}>
      <AbsoluteFill style={{background: 'radial-gradient(1000px 700px at 50% 45%, rgba(40,90,220,0.3), transparent 70%)'}} />
      <Img src={staticFile('logo.png')} style={{height: 230, transform: `scale(${pop(0)})`, marginBottom: 40}} />
      <div style={{width: 220 * rise(10), height: 14, background: COLORS.red, marginBottom: 40}} />
      <div style={{color: COLORS.white, fontWeight: 800, fontSize: 120, opacity: rise(14), transform: `translateY(${(1 - rise(14)) * 40}px)`}}>
        रोज ताज्या बातम्यांसाठी
      </div>
      <div style={{color: COLORS.gold, fontWeight: 800, fontSize: 120, opacity: rise(22), transform: `translateY(${(1 - rise(22)) * 40}px)`}}>
        MahaSpark फॉलो करा
      </div>
      <div
        style={{
          marginTop: 60,
          padding: '22px 70px',
          background: COLORS.red,
          borderRadius: 999,
          color: COLORS.white,
          fontWeight: 800,
          fontSize: 62,
          transform: `scale(${pop(30) * pulse * tap})`,
          boxShadow: '0 12px 50px rgba(225,29,46,0.5)',
        }}
      >
        सबस्क्राईब करा
      </div>
      <div style={{marginTop: 40, color: COLORS.context, fontWeight: 600, fontSize: 48, opacity: rise(40)}}>{CHANNEL_HANDLE}</div>
    </AbsoluteFill>
  );
};
