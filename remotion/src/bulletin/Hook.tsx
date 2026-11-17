import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS} from './constants';

/**
 * The cold open (about 4 s, no voice): the biggest headlines of the bulletin slide in one by one under a red
 * "N big news" bar, so the first seconds already promise what the viewer will get. The steady logo layer sits above.
 */
export const Hook: React.FC<{headlines: string[]; count: number}> = ({headlines, count}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const rise = (delay: number) => spring({frame: frame - delay, fps, config: {damping: 200}});
  const exit = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: `linear-gradient(160deg, ${COLORS.bgTop} 0%, ${COLORS.bgBottom} 100%)`, fontFamily, opacity: exit}}>
      <AbsoluteFill style={{background: 'radial-gradient(1100px 700px at 30% 50%, rgba(40,90,220,0.32), transparent 70%)'}} />
      <div style={{position: 'absolute', left: 120, top: 250, right: 120}}>
        <div
          style={{
            display: 'inline-block',
            padding: '14px 44px',
            background: COLORS.red,
            color: COLORS.white,
            fontWeight: 800,
            fontSize: 70,
            transform: `scaleX(${rise(0)})`,
            transformOrigin: 'left center',
            marginBottom: 46,
          }}
        >
          {`आजच्या ${count} मोठ्या बातम्या`}
        </div>
        {headlines.slice(0, 3).map((headline, i) => (
          <div
            key={i}
            style={{
              color: i === 0 ? COLORS.gold : COLORS.white,
              fontWeight: 800,
              fontSize: 78,
              lineHeight: 1.25,
              marginBottom: 22,
              opacity: rise(8 + i * 10),
              transform: `translateX(${(1 - rise(8 + i * 10)) * 120}px)`,
              borderLeft: `10px solid ${i === 0 ? COLORS.gold : COLORS.red}`,
              paddingLeft: 28,
            }}
          >
            {headline}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
