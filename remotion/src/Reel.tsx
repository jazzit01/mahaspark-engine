import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig} from 'remotion';
import {Backdrop} from './Backdrop';
import {Captions} from './Captions';
import {
  BED_DUCK, BED_VOLUME,
  OUTRO_SECONDS,
  SCENE_EXIT_FRAMES,
  SCENE_LEAD_FRAMES,
  TAIL_SECONDS,
  WHOOSH_LEAD_FRAMES,
  WHOOSH_VOLUME,
} from './constants';
import {Outro} from './bulletin/Outro';
import {SceneCard} from './SceneCard';
import {SharedOverlay} from './SharedOverlay';
import {getStudio} from './studios';
import {getPalette, overMedia} from './theme';
import {Story} from './types';

const BACKDROP_FADE_FRAMES = 9;


/** Frames of the story itself (voice + studio tail); the shared outro follows it. */
export const storyFrames = (story: Story, fps: number): number =>
  Math.max(1, Math.ceil((story.duration_seconds + TAIL_SECONDS) * fps));

/** A 9:16 Short has no outro; the 16:9 video ends with the shared outro. */
export const hasOutro = (story: Story): boolean => story.format !== 'portrait';

export const totalFrames = (story: Story, fps: number): number =>
  storyFrames(story, fps) + (hasOutro(story) ? Math.round(OUTRO_SECONDS * fps) : 0);

/**
 * Layer order (bottom to top):
 *   1. studio motion background, chosen by story.visual_theme
 *   2. per-scene footage / photo (Backdrop), cross-fading from scene to scene
 *   3. scene cards (spring in, scale/fade out), one Sequence per scene
 *   4. karaoke captions synced to story.words
 *   5. SharedOverlay: the logo only, a single steady top-level layer
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
  const outroStart = storyFrames(story, fps);
  const ends = scenes.map((_, i) => (i === scenes.length - 1 ? outroStart : starts[i + 1]));

  const bedFadeStart = durationInFrames - fps;
  // The bed dips while the anchor speaks and swells back in the gaps and the outro.
  const spoken = story.audio === false ? [] : story.words;
  const duck = (f: number) => {
    const t = f / fps;
    let nearest = 1;
    for (const w of spoken) {
      const d = t < w.start ? w.start - t : t > w.end ? t - w.end : 0;
      if (d < nearest) nearest = d;
      if (nearest === 0) break;
    }
    return interpolate(nearest, [0, 0.45], [BED_DUCK, 1], {extrapolateRight: 'clamp'});
  };
  const bedVolume = (f: number) =>
    BED_VOLUME * duck(f) * interpolate(f, [0, fps * 0.5, bedFadeStart, durationInFrames], [0, 1, 1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

  return (
    <AbsoluteFill style={{background: palette.background}}>
      <AbsoluteFill style={story.bg_hue ? {filter: `hue-rotate(${story.bg_hue}deg)`} : undefined}>
        <Studio />
      </AbsoluteFill>

      {scenes.map((scene, i) => {
        if (!scene.media) return null;
        const sceneFrames = Math.max(1, ends[i] - starts[i]);
        const last = i === scenes.length - 1;
        const nextHasMedia = !last && Boolean(scenes[i + 1].media);
        const mountedFrames = sceneFrames + (last ? 0 : BACKDROP_FADE_FRAMES);
        return (
          <Sequence key={`bg-${i}`} from={starts[i]} durationInFrames={mountedFrames} layout="none">
            <Backdrop
              media={scene.media}
              index={i}
              durationInFrames={sceneFrames}
              mountedFrames={mountedFrames}
              fadeOutFrames={last || nextHasMedia ? 0 : BACKDROP_FADE_FRAMES}
              fadeInFrames={i === 0 ? 1 : BACKDROP_FADE_FRAMES}
            />
          </Sequence>
        );
      })}

      {scenes.map((scene, i) => (
        <Sequence key={i} from={starts[i]} durationInFrames={Math.max(1, ends[i] - starts[i])} layout="none">
          <SceneCard
            headline={scene.headline}
            description={scene.description}
            palette={scene.media ? overMedia(palette) : palette}
            durationInFrames={Math.max(SCENE_EXIT_FRAMES + 1, ends[i] - starts[i])}
            index={i}
            total={scenes.length}
            motion={scene.motion}
          />
        </Sequence>
      ))}

      <Captions words={story.caption_words ?? story.words} palette={palette} />

      {/* the steady logo layer covers the story only; the outro shows its own large logo */}
      <Sequence from={0} durationInFrames={outroStart} layout="none">
        <SharedOverlay palette={palette} />
      </Sequence>

      {hasOutro(story) ? (
        <>
          <Sequence from={outroStart} durationInFrames={durationInFrames - outroStart}>
            <Outro />
          </Sequence>
          <Sequence from={Math.max(0, outroStart - WHOOSH_LEAD_FRAMES)} layout="none">
            <Audio src={staticFile('whoosh.wav')} volume={WHOOSH_VOLUME} />
          </Sequence>
        </>
      ) : null}

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
