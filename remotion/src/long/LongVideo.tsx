import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BED_DUCK, BED_VOLUME, WHOOSH_VOLUME} from '../constants';
import {COLORS, WHOOSH_FRAMES_EARLY} from '../bulletin/constants';
import {Outro} from '../bulletin/Outro';
import {getStudio} from '../studios';
import {ExplainerScene} from './ExplainerScenes';
import {LongCaptions} from './LongCaptions';
import {QuestionScene, QuizEnd, QuizIntro} from './QuizScenes';
import {LongBackdrop} from './LongBackdrop';
import {LoopBackdrop} from './LoopBackdrop';
import {LowerThird} from './LowerThird';
import {Sting} from './Sting';
import {TransitionOverlay, transitionKind, useEnterStyle} from './Transitions';
import {packVars} from './kit';
import {LongMedia, LongProps, LongScene} from './types';

const FPS = 30;
const EXIT_FRAMES = 8;
const BACKDROP_FADE = 12;

export const longFrames = (props: LongProps, fps = FPS): number =>
  props.scenes.reduce((sum, s) => sum + Math.max(1, Math.round(s.seconds * fps)), 0) + Math.round(props.outro_seconds * fps);

const SceneBody: React.FC<{scene: LongScene; pin?: LongProps['map']; gallery?: LongMedia[]}> = ({scene, pin, gallery}) => {
  switch (scene.kind) {
    case 'quiz_intro':
      return <QuizIntro scene={scene} />;
    case 'question':
    case 'answer':
      return <QuestionScene scene={scene} />;
    case 'quiz_end':
      return <QuizEnd scene={scene} />;
    default:
      return <ExplainerScene scene={scene} pin={pin} gallery={gallery} />;
  }
};

/** Explainer and daily quiz: scenes in a row on one continuous studio, each with its own voice clip and captions. */
export const LongVideo: React.FC<LongProps> = (props) => {
  const {fps, durationInFrames} = useVideoConfig();
  const starts: number[] = [];
  let cursor = 0;
  props.scenes.forEach((s) => {
    starts.push(cursor);
    cursor += Math.max(1, Math.round(s.seconds * fps));
  });
  const Studio = getStudio(props.studio ?? 'PrimeGridStudio');
  const gallery: LongMedia[] = props.scenes.reduce<LongMedia[]>((all, sc) => (sc.media && !all.some((m) => m.file === sc.media!.file) ? [...all, sc.media] : all), []);
  const outroStart = cursor;
  const outroFrames = Math.round(props.outro_seconds * fps);

  // the bed dips while the anchor speaks (absolute word times = scene start + word time)
  const spoken = props.scenes.flatMap((s, i) => s.words.map((w) => ({start: starts[i] / fps + w.start, end: starts[i] / fps + w.end})));
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
  // a Shorts cut fades the bed in and out around its own window instead of the whole video
  const winStart = props.clip ? Math.round(props.clip.start * fps) : 0;
  const winEnd = props.clip ? Math.round(props.clip.end * fps) : durationInFrames;
  const bedVolume = (f: number) =>
    BED_VOLUME * duck(f) * interpolate(f, [winStart, winStart + fps * 0.5, winEnd - fps, winEnd], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{background: COLORS.bgBottom, ...packVars(props.pack)}}>
      <AbsoluteFill style={props.bg_hue ? {filter: `hue-rotate(${props.bg_hue}deg)`} : undefined}>
        <Studio />
      </AbsoluteFill>
      {props.loop ? <LoopBackdrop file={props.loop} /> : null}

      {/* real photos of the topic: each fades in over the previous one (the overlap), slow Ken Burns push, dark scrim */}
      {props.scenes.map((scene, i) => {
        if (!scene.media) return null;
        const frames = Math.max(1, Math.round(scene.seconds * fps));
        const lead = i > 0 ? BACKDROP_FADE : 0;
        return (
          <Sequence key={`bd${i}`} from={Math.max(0, starts[i] - lead)} durationInFrames={frames + lead} layout="none">
            <LongBackdrop media={scene.media} frames={frames + lead} index={i} fadeIn={lead} />
          </Sequence>
        );
      })}

      {props.scenes.map((scene, i) => {
        const frames = Math.max(1, Math.round(scene.seconds * fps));
        return (
          <Sequence key={i} from={starts[i]} durationInFrames={frames}>
            <AbsoluteFill>
              <FadeOut frames={frames}>
                <Enter kind={i === 0 ? -1 : transitionKind(i)}>
                  <SceneBody scene={scene} pin={props.map} gallery={gallery} />
                </Enter>
                {props.kind === 'explainer' && scene.kind !== 'title' ? <LowerThird text={props.title} /> : null}
              </FadeOut>
              {i > 0 ? <TransitionOverlay kind={transitionKind(i)} /> : null}
              {props.clip || scene.kind === 'question' || scene.kind === 'answer' ? null : <LongCaptions words={scene.words} />}
            </AbsoluteFill>
            <Sequence from={Math.round(scene.lead_seconds * fps)} layout="none">
              <Audio src={staticFile(scene.audio)} />
            </Sequence>
          </Sequence>
        );
      })}

      {props.clip ? null : (
        <Sequence from={0} durationInFrames={Math.round(fps * 1.4)} layout="none">
          <Sting />
        </Sequence>
      )}

      {/* thin progress line over the whole video, then the logo: one steady layer above every scene */}
      <Sequence from={0} durationInFrames={outroStart} layout="none">
        <ProgressLine total={outroStart} />
        <Img src={staticFile('logo.png')} style={{position: 'absolute', left: 72, top: 20, height: 190}} />
      </Sequence>

      {props.clip ? null : (
        <Sequence from={outroStart} durationInFrames={outroFrames}>
          <Outro />
        </Sequence>
      )}

      {starts.slice(1).concat(outroStart).map((from) => (
        <Sequence key={`w${from}`} from={Math.max(0, from - WHOOSH_FRAMES_EARLY)} layout="none">
          <Audio src={staticFile('whoosh.wav')} volume={WHOOSH_VOLUME} />
        </Sequence>
      ))}

      <Audio src={staticFile(`bed/${props.audio_mood}.mp3`)} loop volume={bedVolume} />
    </AbsoluteFill>
  );
};

/** The first frames of a scene: content motion of the cut (the overlay itself is drawn above). kind -1 = none. */
const Enter: React.FC<{kind: number; children: React.ReactNode}> = ({kind, children}) => {
  const style = useEnterStyle(kind < 0 ? 0 : kind);
  return <AbsoluteFill style={kind < 0 ? undefined : style}>{children}</AbsoluteFill>;
};

const FadeOut: React.FC<{frames: number; children: React.ReactNode}> = ({frames, children}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [frames - EXIT_FRAMES, frames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

const ProgressLine: React.FC<{total: number}> = ({total}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 8, background: COLORS.red}}>
      <div style={{width: `${Math.min(1, frame / total) * 100}%`, height: '100%', background: COLORS.gold}} />
    </div>
  );
};
