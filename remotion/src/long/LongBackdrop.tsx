import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

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
        <AbsoluteFill style={{transform: `translateX(${panX}px) scale(${scale})`, transformOrigin: '50% 45%'}}>
          <Img src={staticFile(media.file)} style={fill} />
        </AbsoluteFill>
      )}
      <AbsoluteFill style={{background: 'rgba(10,23,54,0.34)'}} />
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(3,6,16,0.8) 0%, rgba(3,6,16,0.56) 32%, rgba(3,6,16,0.6) 68%, rgba(3,6,16,0.88) 100%)'}} />
    </AbsoluteFill>
  );
};
