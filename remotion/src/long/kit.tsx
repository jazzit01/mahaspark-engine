import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS} from '../bulletin/constants';

/** Content area between the logo/header and the captions (1920x1080). */
export const CONTENT_LEFT = 80;
export const CONTENT_WIDTH = 1760;
export const HEADER_TOP = 205;
export const BODY_TOP = 440;
export const BODY_BOTTOM = 820;

export const devanagari = (n: number | string): string => String(n).replace(/\d/g, (d) => '०१२३४५६७८९'[Number(d)]);

export const CARD: React.CSSProperties = {
  background: 'rgba(8,16,40,0.80)',
  border: '2px solid rgba(245,196,81,0.42)',
  borderRadius: 28,
  boxShadow: '0 14px 46px rgba(0,0,0,0.4)',
};

/** 0 before `cueSeconds`, then a smooth 0 -> 1 (the item appears on the word that names it). */
export const useReveal = (cueSeconds: number, damping = 200): number => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: frame - Math.round(cueSeconds * fps), fps, config: {damping}});
};

export const useSeconds = (): number => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return frame / fps;
};

export const headlineFontSize = (text: string): number => (text.length <= 26 ? 96 : text.length <= 40 ? 84 : 74);

/** The scene headline: big, white, with the animated gold accent bar. Sits in the header zone below the logo. */
export const Headline: React.FC<{text: string; subtitle?: string}> = ({text, subtitle}) => {
  const enter = useReveal(0.1);
  return (
    <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: HEADER_TOP, fontFamily, opacity: enter, transform: `translateY(${(1 - enter) * 24}px)`}}>
      <div style={{width: 150 * enter, height: 10, background: COLORS.red, marginBottom: 16}} />
      <div style={{color: COLORS.white, fontWeight: 800, fontSize: headlineFontSize(text), lineHeight: 1.18, textShadow: '0 4px 22px rgba(0,0,0,0.55)'}}>{text}</div>
      {subtitle ? <div style={{color: COLORS.context, fontWeight: 600, fontSize: 44, marginTop: 8}}>{subtitle}</div> : null}
    </div>
  );
};
