import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {ACCENT, ACCENT2} from './kit';

export const TRANSITION_IN_FRAMES = 14;
export const TRANSITION_KINDS = 3;

/** Which look a cut gets: wipe, zoom-through or light streak, rotating with the scene number (so no two cuts in a row match). */
export const transitionKind = (sceneIndex: number): number => sceneIndex % TRANSITION_KINDS;

/** Content motion at the start of a scene: the zoom-through pushes in from slightly larger. */
export const useEnterStyle = (kind: number): React.CSSProperties => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, TRANSITION_IN_FRAMES], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  if (kind === 1) return {transform: `scale(${1.09 - 0.09 * p})`, opacity: 0.35 + 0.65 * p, transformOrigin: '50% 50%'};
  if (kind === 2) return {transform: `translateX(${(1 - p) * 60}px)`, opacity: 0.3 + 0.7 * p};
  return {opacity: 0.4 + 0.6 * p};
};

/** The overlay of the cut itself (first frames of every scene after the first). */
export const TransitionOverlay: React.FC<{kind: number}> = ({kind}) => {
  const frame = useCurrentFrame();
  if (frame > TRANSITION_IN_FRAMES + 2) return null;
  const p = interpolate(frame, [0, TRANSITION_IN_FRAMES], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  if (kind === 0) {
    // brand-coloured panel sweeps across left to right, leaving a thin bright edge
    const x = interpolate(p, [0, 1], [-105, 105]);
    return (
      <AbsoluteFill style={{pointerEvents: 'none', overflow: 'hidden'}}>
        <div style={{position: 'absolute', top: 0, bottom: 0, left: `${x}%`, width: '100%', background: `linear-gradient(90deg, ${ACCENT2} 0%, ${ACCENT2} 94%, #fff 100%)`, opacity: 0.92}} />
      </AbsoluteFill>
    );
  }
  if (kind === 1) {
    // flash that collapses from the centre
    const a = interpolate(p, [0, 0.25, 1], [0, 0.55, 0]);
    return <AbsoluteFill style={{pointerEvents: 'none', background: `radial-gradient(circle at 50% 50%, rgba(255,255,255,${a}) 0%, rgba(255,255,255,0) ${30 + 55 * p}%)`}} />;
  }
  // diagonal light streak
  const x = interpolate(p, [0, 1], [-60, 160]);
  return (
    <AbsoluteFill style={{pointerEvents: 'none', overflow: 'hidden'}}>
      <div style={{position: 'absolute', top: '-30%', bottom: '-30%', left: `${x}%`, width: '22%', transform: 'skewX(-18deg)', background: `linear-gradient(90deg, rgba(255,255,255,0), ${ACCENT} 45%, #fff 55%, rgba(255,255,255,0))`, opacity: 0.75, filter: 'blur(6px)'}} />
    </AbsoluteFill>
  );
};
