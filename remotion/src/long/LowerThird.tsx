import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS} from '../bulletin/constants';
import {ACCENT, ACCENT2, CONTENT_LEFT} from './kit';

const SHOW_SECONDS = 3.4;

/** "Topic title | MahaSpark ..." -> the part before the first bar or colon-free separator. */
export const topicTag = (title: string): string => title.split(/\s[|｜]\s/)[0].trim();

/** Topic tag in the lower left (between the graphic and the captions): slides in at the start of a scene, then out. */
export const LowerThird: React.FC<{text: string}> = ({text}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const tag = topicTag(text);
  if (!tag) return null;
  const enter = spring({frame: frame - 6, fps, config: {damping: 16, stiffness: 120}});
  const out = interpolate(frame, [(SHOW_SECONDS - 0.4) * fps, SHOW_SECONDS * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  if (frame > SHOW_SECONDS * fps) return null;
  const fontSize = tag.length <= 34 ? 36 : 30;
  return (
    <div style={{position: 'absolute', left: CONTENT_LEFT, top: 836, height: 66, display: 'flex', alignItems: 'stretch', fontFamily, opacity: out, transform: `translateX(${(1 - Math.min(1, enter)) * -140}px)`}}>
      <div style={{width: 10 * Math.min(1, enter), background: ACCENT2}} />
      <div style={{display: 'flex', alignItems: 'center', padding: '0 28px 0 22px', maxWidth: 1100, background: 'rgba(8,14,26,0.82)', borderBottom: `4px solid ${ACCENT}`, color: COLORS.white, fontWeight: 700, fontSize, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{tag}</div>
    </div>
  );
};
