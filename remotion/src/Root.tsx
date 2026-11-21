import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {COMPOSITION_ID, FPS, HEIGHT, SHORT_COMPOSITION_ID, SHORT_HEIGHT, SHORT_WIDTH, WIDTH} from './constants';
import './fonts';
import {Reel, totalFrames} from './Reel';
import {buildSampleStory} from './sampleStory';
import {THEME_NAMES} from './theme';
import {Story} from './types';
import {BulletinReel, bulletinFrames} from './bulletin/BulletinReel';
import {BULLETIN_HEIGHT, BULLETIN_WIDTH} from './bulletin/constants';
import {sampleBulletin} from './bulletin/sampleBulletin';
import {BulletinProps} from './bulletin/types';
import {MahaSparkThumbnail, THUMB_H, THUMB_W} from './Thumb';
import {LongVideo, longFrames} from './long/LongVideo';
import {LongShort, SHORT_H, SHORT_W} from './long/LongShort';
import {LongProps} from './long/types';
import {BulletinThumbnail, THUMB_HEIGHT, THUMB_WIDTH} from './bulletin/Thumbnail';

/** Bulletin length is the sum of its item voiceovers plus the fixed outro (all derived in bulletin.json). */
const calculateBulletinMetadata: CalculateMetadataFunction<BulletinProps> = ({props}) => ({
  durationInFrames: bulletinFrames(props, FPS),
  fps: FPS,
  width: BULLETIN_WIDTH,
  height: BULLETIN_HEIGHT,
});

/** Explainer / quiz length is the sum of its scenes plus the fixed outro (all derived in long.json). */
const calculateLongMetadata: CalculateMetadataFunction<LongProps> = ({props}) => ({
  durationInFrames: longFrames(props, FPS),
  fps: FPS,
  width: BULLETIN_WIDTH,
  height: BULLETIN_HEIGHT,
});

/** A Shorts cut of a long video: the length of its clip window, vertical. */
const calculateLongShortMetadata: CalculateMetadataFunction<LongProps> = ({props}) => ({
  durationInFrames: Math.max(1, Math.round(((props.clip?.end ?? 30) - (props.clip?.start ?? 0)) * FPS)),
  fps: FPS,
  width: SHORT_W,
  height: SHORT_H,
});

const sampleLong: LongProps = {
  kind: 'explainer',
  title: 'नमुना',
  audio_mood: 'neutral',
  bg_hue: 0,
  outro_seconds: 8,
  outro_start: 6,
  total_seconds: 14,
  scenes: [
    {
      kind: 'points', headline: 'मुख्य मुद्दे', items: [{label: 'पहिला मुद्दा', cue: 1}, {label: 'दुसरा मुद्दा', cue: 2.5}],
      audio: 'whoosh.wav', audio_seconds: 4, lead_seconds: 0.5, seconds: 6, start: 0,
      words: [{text: 'पहिला', start: 1, end: 1.4}, {text: 'मुद्दा.', start: 1.4, end: 2}],
    },
  ],
};

/** Video length follows the real voiceover: duration_seconds (from faster-whisper) plus a short studio tail. */
const calculateMetadata: CalculateMetadataFunction<Story> = ({props}) => ({
  durationInFrames: totalFrames(props, FPS),
  fps: FPS,
  width: WIDTH,
  height: HEIGHT,
});

/** The 9:16 Short (thin stories): same component and graphics, vertical size, no outro. */
const calculateShortMetadata: CalculateMetadataFunction<Story> = ({props}) => ({
  durationInFrames: totalFrames({...props, format: 'portrait'}, FPS),
  fps: FPS,
  width: SHORT_WIDTH,
  height: SHORT_HEIGHT,
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id={SHORT_COMPOSITION_ID}
        component={Reel}
        width={SHORT_WIDTH}
        height={SHORT_HEIGHT}
        fps={FPS}
        durationInFrames={FPS * 20}
        defaultProps={{...buildSampleStory('PrimeGridStudio'), format: 'portrait' as const}}
        calculateMetadata={calculateShortMetadata}
      />

      {/* Production composition: rendered with --props=public/story.json. */}
      <Composition
        id={COMPOSITION_ID}
        component={Reel}
        width={WIDTH}
        height={HEIGHT}
        fps={FPS}
        durationInFrames={FPS * 30}
        defaultProps={buildSampleStory('PrimeGridStudio')}
        calculateMetadata={calculateMetadata}
      />

      {/* Long 16:9 news bulletin: rendered with --props=public/bulletin.json. */}
      <Composition
        id="MahaSparkBulletin"
        component={BulletinReel}
        width={BULLETIN_WIDTH}
        height={BULLETIN_HEIGHT}
        fps={FPS}
        durationInFrames={FPS * 38}
        defaultProps={sampleBulletin}
        calculateMetadata={calculateBulletinMetadata}
      />

      {/* Explainer and daily quiz (16:9): rendered with --props=public/long.json. */}
      <Composition
        id="MahaSparkLong"
        component={LongVideo}
        width={BULLETIN_WIDTH}
        height={BULLETIN_HEIGHT}
        fps={FPS}
        durationInFrames={FPS * 14}
        defaultProps={sampleLong}
        calculateMetadata={calculateLongMetadata}
      />

      {/* 9:16 Shorts cut of an explainer or quiz: rendered with --props=public/long_short.json (long.json + a `clip` window). */}
      <Composition
        id="MahaSparkLongShort"
        component={LongShort}
        width={SHORT_W}
        height={SHORT_H}
        fps={FPS}
        durationInFrames={FPS * 30}
        defaultProps={{...sampleLong, clip: {start: 0, end: 14}}}
        calculateMetadata={calculateLongShortMetadata}
      />

      {/* YouTube thumbnail variants (style: bold | question | figure | alert): rendered with --props=public/thumb_<style>.json. */}
      <Composition
        id="MahaSparkThumbnail"
        component={MahaSparkThumbnail}
        width={THUMB_W}
        height={THUMB_H}
        fps={FPS}
        durationInFrames={1}
        defaultProps={{text: 'पाणी योजना मंजूर?', tag: 'समजून घ्या', figure: '₹१,२०० कोटी', photo: null, style: 'bold' as const, hue: 0}}
      />

      {/* YouTube thumbnail still for the bulletin: rendered with --props=public/bulletin_thumb.json. */}
      <Composition
        id="BulletinThumbnail"
        component={BulletinThumbnail}
        width={THUMB_WIDTH}
        height={THUMB_HEIGHT}
        fps={FPS}
        durationInFrames={1}
        defaultProps={{headline: sampleBulletin.items[0].headline, count: 10, photo: null}}
      />

      {/* One preview composition per studio, for design work in Remotion Studio. */}
      {THEME_NAMES.map((theme) => (
        <Composition
          key={theme}
          id={`Preview-${theme}`}
          component={Reel}
          width={WIDTH}
          height={HEIGHT}
          fps={FPS}
          durationInFrames={FPS * 30}
          defaultProps={buildSampleStory(theme)}
          calculateMetadata={calculateMetadata}
        />
      ))}
    </>
  );
};
