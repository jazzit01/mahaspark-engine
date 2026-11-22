import React from 'react';
import {AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame} from 'remotion';

type Props = {
  media: {file: string; width: number; height: number};
  /** Frames this backdrop stays mounted (its Sequence). */
  frames: number;
  /** Alternates the slow-zoom direction between scenes. */
  index: number;
  /** Frames over which it fades in on top of the previous scene's photo (0 = none). */
  fadeIn: number;
};

/**
 * A real photo of the topic behind a scene: slow push-in or pull-out with a small sideways drift, a dark brand-blue scrim
 * (heavier at the top and bottom) so the graphics and captions stay readable. Portrait photos are shown whole over a
 * blurred, darkened copy of themselves.
 */
export const LongBackdrop: React.FC<Props> = ({media, frames, index, fadeIn}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [0, Math.max(1, frames)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const zoomIn = index % 2 === 0;
  const scale = zoomIn ? 1.05 + 0.1 * progress : 1.15 - 0.1 * progress;
  const panX = (zoomIn ? -1 : 1) * 34 * progress;
  const opacity = fadeIn > 0 ? interpolate(frame, [0, fadeIn], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
  const portrait = media.height > media.width * 1.05;
  const fill: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover'};
  return (
    <AbsoluteFill style={{opacity, overflow: 'hidden', background: '#05070d'}}>
      {portrait ? (
        <>
          <AbsoluteFill style={{transform: 'scale(1.25)'}}>
            <Img src={staticFile(media.file)} style={{...fill, filter: 'blur(40px) brightness(0.55) saturate(1.2)'}} />
          </AbsoluteFill>
          <AbsoluteFill style={{transform: `translateX(${panX}px) scale(${1 + 0.06 * (zoomIn ? progress : 1 - progress)})`}}>
            <Img src={staticFile(media.file)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
          </AbsoluteFill>
        </>
      ) : (
        <>
          {/* depth parallax (layers, not a cut-out): a blurred far layer drifts against a feathered sharp near layer */}
          <AbsoluteFill style={{transform: `translateX(${-panX * 0.5}px) scale(${1.32 - 0.04 * progress})`}}>
            <Img src={staticFile(media.file)} style={{...fill, filter: 'blur(34px) brightness(0.6) saturate(1.2)'}} />
          </AbsoluteFill>
          <AbsoluteFill style={{transform: `translateX(${panX * 1.6}px) scale(${scale})`, transformOrigin: '50% 45%', WebkitMaskImage: 'radial-gradient(ellipse 72% 70% at 50% 48%, #000 55%, transparent 100%)', maskImage: 'radial-gradient(ellipse 72% 70% at 50% 48%, #000 55%, transparent 100%)'}}>
            <Img src={staticFile(media.file)} style={fill} />
          </AbsoluteFill>
          <Motes frame={frame} index={index} />
        </>
      )}
      <AbsoluteFill style={{background: 'rgba(10,23,54,0.34)'}} />
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(3,6,16,0.8) 0%, rgba(3,6,16,0.56) 32%, rgba(3,6,16,0.6) 68%, rgba(3,6,16,0.88) 100%)'}} />
    </AbsoluteFill>
  );
};

/** A few slow, faint light motes drifting upward in front of the photo (the near-most layer of the depth effect). */
const Motes: React.FC<{frame: number; index: number}> = ({frame, index}) => (
  <AbsoluteFill style={{pointerEvents: 'none'}}>
    {Array.from({length: 14}, (_, i) => {
      const x = random(`mx${index}-${i}`) * 100;
      const size = 5 + random(`ms${index}-${i}`) * 9;
      const speed = 0.25 + random(`mv${index}-${i}`) * 0.5;
      const y = (130 - ((frame * speed + random(`my${index}-${i}`) * 130) % 130));
      return <div key={i} style={{position: 'absolute', left: `${x}%`, top: `${y - 15}%`, width: size, height: size, borderRadius: '50%', background: 'rgba(255,244,214,0.9)', opacity: 0.22 + 0.2 * random(`mo${index}-${i}`), filter: 'blur(1px)'}} />;
    })}
  </AbsoluteFill>
);
