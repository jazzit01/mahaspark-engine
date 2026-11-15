import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {COMPOSITION_ID, FPS, HEIGHT, WIDTH} from './constants';
import './fonts';
import {Reel, totalFrames} from './Reel';
import {buildSampleStory} from './sampleStory';
import {THEME_NAMES} from './theme';
import {Story} from './types';
import {BulletinReel, bulletinFrames} from './bulletin/BulletinReel';
import {BULLETIN_HEIGHT, BULLETIN_WIDTH} from './bulletin/constants';
import {sampleBulletin} from './bulletin/sampleBulletin';
import {BulletinProps} from './bulletin/types';
import {BulletinThumbnail, THUMB_HEIGHT, THUMB_WIDTH} from './bulletin/Thumbnail';

/** Bulletin length is the sum of its item voiceovers plus the fixed outro (all derived in bulletin.json). */
const calculateBulletinMetadata: CalculateMetadataFunction<BulletinProps> = ({props}) => ({
  durationInFrames: bulletinFrames(props, FPS),
  fps: FPS,
  width: BULLETIN_WIDTH,
  height: BULLETIN_HEIGHT,
});

/** Video length follows the real voiceover: duration_seconds (from faster-whisper) plus a short studio tail. */
const calculateMetadata: CalculateMetadataFunction<Story> = ({props}) => ({
  durationInFrames: totalFrames(props, FPS),
  fps: FPS,
  width: WIDTH,
  height: HEIGHT,
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
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
