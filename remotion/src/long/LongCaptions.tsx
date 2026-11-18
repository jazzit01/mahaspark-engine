import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {LongWord} from './types';

const MAX_WORDS = 6;

/** Word-by-word karaoke captions for one scene (times in seconds from the scene start), same look as the reels. */
export const LongCaptions: React.FC<{words: LongWord[]}> = ({words}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const chunks: LongWord[][] = [];
  let cur: LongWord[] = [];
  words.forEach((w, i) => {
    cur.push(w);
    if (cur.length >= MAX_WORDS || /[.]$/.test(w.text) || (/[,]$/.test(w.text) && cur.length >= 3) || i === words.length - 1) {
      chunks.push(cur);
      cur = [];
    }
  });
  let index = -1;
  chunks.forEach((c, i) => {
    if (t >= c[0].start - 0.05) index = i;
  });
  const chunk = index >= 0 ? chunks[index] : null;
  if (!chunk || t > chunk[chunk.length - 1].end + 0.6) return null;
  return (
    <div style={{position: 'absolute', left: 80, right: 80, bottom: 56, display: 'flex', justifyContent: 'center', fontFamily}}>
      <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', columnGap: 18, rowGap: 6, padding: '16px 34px 20px', borderRadius: 24, background: 'rgba(8,14,26,0.78)', border: '1px solid rgba(245,196,81,0.4)', boxShadow: '0 10px 34px rgba(0,0,0,0.4)', maxWidth: 1500}}>
        {chunk.map((w, i) => {
          const active = t >= w.start && t < w.end;
          const spoken = t >= w.end;
          return (
            <span key={`${index}-${i}`} style={{color: active ? '#F5C451' : spoken ? '#F8FAFC' : 'rgba(248,250,252,0.55)', fontSize: 54, fontWeight: active ? 800 : 700, lineHeight: 1.35, display: 'inline-block', transform: `scale(${active ? 1.08 : 1})`, textShadow: '0 2px 10px rgba(0,0,0,0.55)'}}>
              {w.text.replace(/[.,]+$/, '')}
            </span>
          );
        })}
      </div>
    </div>
  );
};
