import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, staticFile} from 'remotion';
import {BED_VOLUME, WHOOSH_VOLUME} from '../constants';
import {COLORS, WHOOSH_FRAMES_EARLY, itemFrames} from './constants';
import {ItemScreen} from './ItemScreen';
import {Outro} from './Outro';
import {Ticker} from './Ticker';
import {BulletinProps} from './types';

const FPS = 30;

export const bulletinFrames = (props: BulletinProps, fps = FPS): number =>
  props.items.reduce((sum, item) => sum + itemFrames(item.seconds, fps), 0) + itemFrames(props.outro_seconds, fps);

export const BulletinReel: React.FC<BulletinProps> = (props) => {
  const fps = FPS;
  const total = bulletinFrames(props, fps);
  const starts: number[] = [];
  let cursor = 0;
  props.items.forEach((item) => {
    starts.push(cursor);
    cursor += itemFrames(item.seconds, fps);
  });
  const outroStart = cursor;
  const outroFrames = itemFrames(props.outro_seconds, fps);

  return (
    <AbsoluteFill style={{background: COLORS.bgBottom}}>
      {props.items.map((item, i) => {
        const frames = itemFrames(item.seconds, fps);
        const upcoming = props.items.slice(i + 1).map((it) => it.headline);
        const ticker = upcoming.length ? upcoming : props.items.map((it) => it.headline);
        return (
          <Sequence key={i} from={starts[i]} durationInFrames={frames}>
            <ItemScreen item={item} frames={frames} hue={(props.bg_hue ?? 0) + (i % 4) * 18} />
            <Ticker headlines={ticker} label={upcoming.length ? 'पुढील बातम्या' : 'आजच्या बातम्या'} offset={starts[i]} total={total} />
            <Sequence from={Math.round(item.lead_seconds * fps)} layout="none">
              <Audio src={staticFile(item.audio)} />
            </Sequence>
          </Sequence>
        );
      })}
      {/* logo: one steady layer above every item, so it never moves across cuts (the outro shows its own) */}
      <Sequence from={0} durationInFrames={outroStart} layout="none">
        <Img src={staticFile('logo.png')} style={{position: 'absolute', left: 72, top: 20, height: 190}} />
      </Sequence>

      <Sequence from={outroStart} durationInFrames={outroFrames}>
        <Outro />
      </Sequence>

      {/* whoosh on every cut, a little ahead of the wipe's peak */}
      {starts.slice(1).concat(outroStart).map((from) => (
        <Sequence key={`w${from}`} from={Math.max(0, from - WHOOSH_FRAMES_EARLY)} layout="none">
          <Audio src={staticFile('whoosh.wav')} volume={WHOOSH_VOLUME} />
        </Sequence>
      ))}

      <Audio
        src={staticFile('bed/neutral.mp3')}
        loop
        volume={(f) => BED_VOLUME * Math.min(1, Math.max(0, (total - f) / fps))}
      />
    </AbsoluteFill>
  );
};
