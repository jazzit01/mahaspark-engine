import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS} from '../bulletin/constants';
import {getStudio} from '../studios';
import {LongVideo} from './LongVideo';
import {KineticText} from './kit';
import {LongProps, LongWord} from './types';

export const SHORT_W = 1080;
export const SHORT_H = 1920;
const SCALE = SHORT_W / 1920; // the 16:9 video fills the full width of the vertical frame
const VIDEO_TOP = 400;
const MAX_WORDS = 4;

/** Big karaoke captions under the video, from the absolute word times of every scene in the clip. */
const ShortCaptions: React.FC<{props: LongProps}> = ({props}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const clip = props.clip!;
  const t = clip.start + frame / fps;
  const words: LongWord[] = props.scenes.flatMap((s) => s.words.map((w) => ({...w, start: s.start + w.start, end: s.start + w.end})));
  const inClip = words.filter((w) => w.end > clip.start && w.start < clip.end);
  const chunks: LongWord[][] = [];
  let cur: LongWord[] = [];
  inClip.forEach((w, i) => {
    cur.push(w);
    if (cur.length >= MAX_WORDS || /[.]$/.test(w.text) || (/[,]$/.test(w.text) && cur.length >= 2) || i === inClip.length - 1) {
      chunks.push(cur);
      cur = [];
    }
  });
  let index = -1;
  chunks.forEach((c, i) => {
    if (t >= c[0].start - 0.05) index = i;
  });
  const chunk = index >= 0 ? chunks[index] : null;
  if (!chunk || t > chunk[chunk.length - 1].end + 0.5) return null;
  return (
    <div style={{position: 'absolute', left: 60, right: 60, top: VIDEO_TOP + 1080 * SCALE + 110, display: 'flex', justifyContent: 'center', fontFamily}}>
      <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', columnGap: 22, rowGap: 8, padding: '22px 36px 26px', borderRadius: 30, background: 'rgba(8,14,26,0.82)', border: '2px solid rgba(245,196,81,0.45)'}}>
        {chunk.map((w, i) => {
          const active = t >= w.start && t < w.end;
          return (
            <span key={`${index}-${i}`} style={{color: active ? '#F5C451' : t >= w.end ? '#F8FAFC' : 'rgba(248,250,252,0.55)', fontSize: 84, fontWeight: active ? 800 : 700, lineHeight: 1.3, display: 'inline-block', transform: `scale(${active ? 1.08 : 1})`}}>
              {w.text.replace(/[.,]+$/, '')}
            </span>
          );
        })}
      </div>
    </div>
  );
};

/** 9:16 Shorts cut: the title on top, the (scaled) long video in the middle, big captions underneath. Props = long.json + `clip`. */
export const LongShort: React.FC<LongProps> = (props) => {
  const {fps} = useVideoConfig();
  const clip = props.clip ?? {start: 0, end: 30};
  const Studio = getStudio(props.studio ?? 'PrimeGridStudio');
  const from = Math.round(clip.start * fps);
  return (
    <AbsoluteFill style={{background: COLORS.bgBottom}}>
      <AbsoluteFill style={props.bg_hue ? {filter: `hue-rotate(${props.bg_hue}deg)`} : undefined}>
        <Studio />
      </AbsoluteFill>
      <div style={{position: 'absolute', left: 60, right: 60, top: 130, height: 240, fontFamily, display: 'flex', alignItems: 'center'}}>
        <KineticText text={props.title} startSeconds={0.1} style={{color: COLORS.white, fontWeight: 800, fontSize: props.title.length <= 30 ? 84 : 68, lineHeight: 1.18, textShadow: '0 4px 22px rgba(0,0,0,0.55)'}} />
      </div>
      <div style={{position: 'absolute', left: 0, top: VIDEO_TOP, width: 1920, height: 1080, transform: `scale(${SCALE})`, transformOrigin: '0 0', overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,0.5)'}}>
        <Sequence from={-from} layout="none">
          <LongVideo {...props} clip={clip} />
        </Sequence>
      </div>
      <ShortCaptions props={{...props, clip}} />
    </AbsoluteFill>
  );
};
