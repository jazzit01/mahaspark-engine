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

/** Brand style packs: one accent pair per series, set as CSS variables on the video root (see packVars). */
export const PACKS: Record<string, {accent: string; accent2: string}> = {
  news: {accent: '#f5c451', accent2: '#e11d2e'},
  knowledge: {accent: '#f5c451', accent2: '#e11d2e'},
  quiz: {accent: '#22d3ee', accent2: '#f97316'},
};
export const packVars = (pack?: string): React.CSSProperties =>
  ({'--accent': (PACKS[pack ?? 'knowledge'] ?? PACKS.knowledge).accent, '--accent2': (PACKS[pack ?? 'knowledge'] ?? PACKS.knowledge).accent2} as React.CSSProperties);
export const ACCENT = 'var(--accent, #f5c451)';
export const ACCENT2 = 'var(--accent2, #e11d2e)';

export const CARD: React.CSSProperties = {
  background: 'rgba(8,16,40,0.80)',
  border: '2px solid color-mix(in srgb, var(--accent, #f5c451) 42%, transparent)',
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

/** Index of the word to highlight in gold: the first word holding a figure, else the longest word (3+ words only). */
export const keyWordIndex = (words: string[]): number => {
  const digit = words.findIndex((w) => /[0-9०-९]/.test(w));
  if (digit >= 0) return digit;
  if (words.length < 3) return -1;
  let best = 0;
  words.forEach((w, i) => {
    if (w.length > words[best].length) best = i;
  });
  return words[best].length >= 5 ? best : -1;
};

/** Headline text whose words spring in one after another; the key word turns gold. Words are never split. */
export const KineticText: React.FC<{text: string; startSeconds?: number; stagger?: number; style?: React.CSSProperties}> = ({text, startSeconds = 0.1, stagger = 0.07, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = text.split(/\s+/).filter(Boolean);
  const key = keyWordIndex(words);
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', columnGap: '0.28em', rowGap: 0, ...style}}>
      {words.map((w, i) => {
        const p = spring({frame: frame - Math.round((startSeconds + i * stagger) * fps), fps, config: {damping: 14, stiffness: 150, mass: 0.7}});
        const pc = Math.min(1, Math.max(0, p));
        return (
          <span key={i} style={{display: 'inline-block', opacity: pc, transform: `translateY(${(1 - p) * 46}px) scale(${0.86 + 0.14 * p})`, color: i === key ? ACCENT : style?.color, textShadow: i === key ? '0 4px 30px color-mix(in srgb, var(--accent, #f5c451) 45%, transparent)' : undefined}}>{w}</span>
        );
      })}
    </div>
  );
};

/** The scene headline: big, white, kinetic words, with the animated red accent bar. Sits in the header zone below the logo. */
export const Headline: React.FC<{text: string; subtitle?: string}> = ({text, subtitle}) => {
  const enter = useReveal(0.1);
  const subtitleIn = useReveal(0.1 + 0.07 * text.split(/\s+/).length);
  return (
    <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: HEADER_TOP, fontFamily}}>
      <div style={{width: 150 * enter, height: 10, background: ACCENT2, marginBottom: 16}} />
      <KineticText text={text} style={{color: COLORS.white, fontWeight: 800, fontSize: headlineFontSize(text), lineHeight: 1.18, textShadow: '0 4px 22px rgba(0,0,0,0.55)'}} />
      {subtitle ? <div style={{color: COLORS.context, fontWeight: 600, fontSize: 44, marginTop: 8, opacity: subtitleIn}}>{subtitle}</div> : null}
    </div>
  );
};
