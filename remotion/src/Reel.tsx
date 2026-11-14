import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig} from 'remotion';
import {Captions} from './Captions';
import {
  BED_VOLUME,
  SCENE_EXIT_FRAMES,
  SCENE_LEAD_FRAMES,
  TAIL_SECONDS,
  WHOOSH_LEAD_FRAMES,
  WHOOSH_VOLUME,
} from './constants';
import {SceneCard, Fact} from './SceneCard';
import {SharedOverlay} from './SharedOverlay';
import {getStudio} from './studios';
import {getPalette} from './theme';
import {Story} from './types';

const FACT_PLAN: string[][] = [['where', 'when'], ['who'], ['why', 'how'], ['where'], ['when'], ['who']];

/** The 5W1H chips shown under a scene's context card (empty answers are skipped). */
const factsForScene = (index: number, five?: Record<string, string>): Fact[] =>
  (FACT_PLAN[index] ?? [])
    .map((key) => ({value: (five?.[key] ?? '').trim()}))
    .filter((fact) => fact.value.length > 0 && fact.value.length <= 90);

export const totalFrames = (story: Story, fps: number): number =>
  Math.max(1, Math.ceil((story.duration_seconds + TAIL_SECONDS) * fps));

/**
 * Layer order (bottom to top):
 *   1. studio motion background, chosen by story.visual_theme
 *   2. scene cards (spring in, scale/fade out), one Sequence per scene
 *   3. karaoke captions synced to story.words
 *   4. SharedOverlay: logo + category pill, a single steady top-level layer
 * Audio: anchor voiceover, studio bed at -20 dB, and a whoosh on every scene cut.
 */
export const Reel: React.FC<Story> = (story) => {
  const {fps, durationInFrames} = useVideoConfig();
  const palette = getPalette(story.visual_theme);
  const Studio = getStudio(story.visual_theme);

  const scenes = story.scenes;
  const starts = scenes.map((scene, i) =>
    i === 0 ? 0 : Math.max(0, Math.round(scene.start * fps) - SCENE_LEAD_FRAMES),
  );
  const ends = scenes.map((_, i) => (i === scenes.length - 1 ? durationInFrames : starts[i + 1]));

  const bedFadeStart = durationInFrames - fps;
  const bedVolume = (f: number) =>
    BED_VOLUME * interpolate(f, [0, fps * 0.5, bedFadeStart, durationInFrames], [0, 1, 1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

  return (
    <AbsoluteFill style={{background: palette.background}}>
      <AbsoluteFill>
        <Studio />
      </AbsoluteFill>

      {scenes.map((scene, i) => (
        <Sequence key={i} from={starts[i]} durationInFrames={Math.max(1, ends[i] - starts[i])} layout="none">
          <SceneCard
            headline={scene.headline}
            description={scene.description}
            palette={palette}
            durationInFrames={Math.max(SCENE_EXIT_FRAMES + 1, ends[i] - starts[i])}
            index={i}
            total={scenes.length}
            facts={factsForScene(i, story.five_w_one_h)}
          />
        </Sequence>
      ))}

      <Captions words={story.words} palette={palette} />

      <SharedOverlay category={story.category} palette={palette} />

      {story.audio === false ? null : <Audio src={staticFile('voiceover.wav')} />}
      <Audio src={staticFile(`bed/${story.audio_mood}.mp3`)} loop volume={bedVolume} />
      {scenes.map((_, i) =>
        i === 0 ? null : (
          <Sequence key={`whoosh-${i}`} from={Math.max(0, starts[i] - WHOOSH_LEAD_FRAMES)} layout="none">
            <Audio src={staticFile('whoosh.wav')} volume={WHOOSH_VOLUME} />
          </Sequence>
        ),
      )}
    </AbsoluteFill>
  );
};
