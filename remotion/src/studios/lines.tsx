import React from 'react';

/** Shared helpers for the line-art studios (chalkboard, blueprint, data map, light & lines). */

/** Draw-on progress (0..1) of something that starts at `start` seconds and takes `duration` seconds. */
export const drawn = (t: number, start: number, duration: number): number => Math.min(1, Math.max(0, (t - start) / duration));

/** 0..1..0 envelope of a repeating item: fades in over `fadeIn`, holds, fades out over `fadeOut` at the end of `period`. */
export const cycleOpacity = (phase: number, period: number, fadeIn = 0.6, fadeOut = 1.6): number => {
  const p = ((phase % period) + period) % period;
  if (p < fadeIn) return p / fadeIn;
  if (p > period - fadeOut) return Math.max(0, (period - p) / fadeOut);
  return 1;
};

/** A path that draws itself: pathLength 1, dash offset follows `progress`. */
export const DrawPath: React.FC<{d: string; progress: number; stroke: string; width?: number; opacity?: number; filter?: string; fill?: string}> = ({
  d, progress, stroke, width = 3, opacity = 1, filter, fill = 'none',
}) => (
  <path d={d} pathLength={1} fill={fill} stroke={stroke} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={1} strokeDashoffset={1 - progress} opacity={opacity} filter={filter} />
);
