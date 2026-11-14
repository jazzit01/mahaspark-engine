import React from 'react';
import {AbsoluteFill, Img, Loop, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneMedia} from './types';

type Props = {
  media: SceneMedia;
  /** Frames of this scene (drives the slow zoom). */
  durationInFrames: number;
  /** Frames this backdrop stays mounted (its Sequence length: the scene plus the overlap with the next one). */
  mountedFrames: number;
  /** Frames over which it fades out at the end of the mount; 0 when the next scene's footage takes over. */
  fadeOutFrames: number;
  /** Alternates the slow-zoom direction between scenes. */
  index: number;
  /** Frames over which the backdrop fades in (the previous one stays underneath until then). */
  fadeInFrames: number;
};

/**
 * Per-scene footage or photo, full-bleed behind the cards: slow Ken Burns push, a fade-in over the previous
 * scene, and a dark scrim (heavier at the top and bottom) so text stays readable on any clip.
 * Videos loop when the scene is longer than the clip; they are always muted (the anchor and the bed own the audio).
 */
export const Backdrop: React.FC<Props> = ({media, durationInFrames, mountedFrames, fadeOutFrames, index, fadeInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const progress = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const zoomIn = index % 2 === 0;
  const scale = media.type === 'image' ? (zoomIn ? 1.04 + 0.12 * progress : 1.16 - 0.12 * progress) : 1.04 + 0.07 * progress;
  const panX = (zoomIn ? -1 : 1) * 14 * progress;
  const fadeIn = interpolate(frame, [0, fadeInFrames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeOut =
    fadeOutFrames > 0
      ? interpolate(frame, [mountedFrames - fadeOutFrames, mountedFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
      : 1;
  const opacity = fadeIn * fadeOut;

  const fill: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 30%'};
  const clipFrames = Math.max(1, Math.round((media.duration ?? 8) * fps));

  return (
    <AbsoluteFill style={{opacity, overflow: 'hidden', background: '#05070d'}}>
      <AbsoluteFill style={{transform: `translateX(${panX}px) scale(${scale})`, transformOrigin: '50% 40%'}}>
        {media.type === 'video' ? (
          <Loop durationInFrames={clipFrames}>
            <OffthreadVideo src={staticFile(media.file)} muted style={fill} />
          </Loop>
        ) : (
          <Img src={staticFile(media.file)} style={fill} />
        )}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(3,5,10,0.72) 0%, rgba(3,5,10,0.38) 22%, rgba(3,5,10,0.34) 55%, rgba(3,5,10,0.5) 75%, rgba(3,5,10,0.8) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};
