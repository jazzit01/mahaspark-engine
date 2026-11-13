import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {COMPOSITION_ID, FPS, HEIGHT, WIDTH} from './constants';
import './fonts';
import {Reel, totalFrames} from './Reel';
import {buildSampleStory} from './sampleStory';
import {THEME_NAMES} from './theme';
import {Story} from './types';

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
