import React from 'react';
import {fontFamily} from '../fonts';
import {COLORS} from '../bulletin/constants';
import {LongScene} from './types';
import {interpolateColors} from 'remotion';
import {ACCENT, ACCENT2, CARD, CONTENT_LEFT, CONTENT_WIDTH, devanagari, useReveal, useSeconds} from './kit';

const GREEN = '#22c55e';

const Big: React.FC<{scene: LongScene; closing?: boolean}> = ({scene, closing}) => {
  const p = useReveal(0.15);
  const sub = useReveal(0.8);
  const t = useSeconds();
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', padding: '100px 120px 220px', fontFamily}}>
      <div style={{color: ACCENT, fontWeight: 800, fontSize: 300, lineHeight: 0.9, opacity: p, transform: `scale(${0.8 + 0.2 * p}) rotate(${Math.sin(t * 2) * 3}deg)`}}>{closing ? '★' : '?'}</div>
      <div style={{color: COLORS.white, fontWeight: 800, fontSize: 128, lineHeight: 1.15, opacity: p, textShadow: '0 6px 30px rgba(0,0,0,0.6)'}}>{scene.headline}</div>
      <div style={{width: 260 * p, height: 12, background: ACCENT2, margin: '26px 0'}} />
      {scene.subtitle ? <div style={{color: ACCENT, fontWeight: 700, fontSize: 58, opacity: sub}}>{scene.subtitle}</div> : null}
    </div>
  );
};

/** Countdown ring: counts down only during the silent seconds after the voice has read the options.
 * The ring shifts from cyan through amber to red as time runs out and pulses in the last two seconds. */
const Timer: React.FC<{scene: LongScene}> = ({scene}) => {
  const t = useSeconds();
  const total = scene.extra_seconds ?? 5;
  const start = scene.lead_seconds + scene.audio_seconds;
  const left = Math.min(total, Math.max(0, total - (t - start)));
  const running = t >= start;
  const shown = running ? Math.ceil(left) : total;
  const size = 150;
  const radius = 62;
  const circ = 2 * Math.PI * radius;
  const frac = running ? left / total : 1;
  const urgent = running && left <= 2;
  const color = interpolateColors(frac, [0, 0.4, 1], ['#ef4444', '#f59e0b', '#22d3ee']);
  const beat = urgent ? 1 + 0.07 * Math.abs(Math.sin(left * Math.PI)) : 1;
  return (
    <div style={{position: 'absolute', right: 80, top: 215, width: size, height: size, fontFamily, transform: `scale(${beat})`}}>
      <svg width={size} height={size} viewBox="0 0 150 150" style={{position: 'absolute', transform: 'rotate(-90deg)', filter: urgent ? `drop-shadow(0 0 14px ${color})` : undefined}}>
        <circle cx={75} cy={75} r={radius} stroke="rgba(255,255,255,0.18)" strokeWidth={12} fill="rgba(8,16,40,0.8)" />
        <circle cx={75} cy={75} r={radius} stroke={color} strokeWidth={12} fill="none" strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - frac)} />
      </svg>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: urgent ? color : COLORS.white, fontWeight: 800, fontSize: 74, opacity: running || left === total ? 1 : 0.6}}>{devanagari(shown)}</div>
    </div>
  );
};

/** One dot per question: answered ones filled, the current one ringed (a running progress bar for the quiz). */
const QuizDots: React.FC<{current: number; total: number; done: boolean}> = ({current, total, done}) => (
  <div style={{display: 'flex', gap: 12, alignItems: 'center'}}>
    {Array.from({length: total}, (_, i) => {
      const filled = i + 1 < current || (done && i + 1 === current);
      const now = i + 1 === current;
      return <div key={i} style={{width: now ? 26 : 20, height: now ? 26 : 20, borderRadius: '50%', background: filled ? ACCENT : 'transparent', border: `4px solid ${filled || now ? ACCENT : 'rgba(255,255,255,0.35)'}`, boxShadow: now ? `0 0 16px ${ACCENT}` : undefined}} />;
    })}
  </div>
);

const OPTION_W = 860;
const OPTION_H = 142;

const Option: React.FC<{letter: string; text: string; cue: number; state: 'idle' | 'correct' | 'wrong'}> = ({letter, text, cue, state}) => {
  const p = Math.min(1, useReveal(cue, 16));
  const glow = state === 'correct' ? 0.5 + 0.5 * Math.sin(useSeconds() * 5) : 0;
  const color = state === 'correct' ? GREEN : state === 'wrong' ? 'rgba(255,255,255,0.72)' : COLORS.white;
  return (
    <div style={{...CARD, width: OPTION_W, height: OPTION_H, display: 'flex', alignItems: 'center', gap: 26, padding: '0 30px', opacity: state === 'wrong' ? 0.8 : p, transform: `translateY(${(1 - p) * 30}px) scale(${state === 'correct' ? 1.03 : 1})`, boxShadow: state === 'correct' ? `0 0 ${24 + 30 * glow}px rgba(34,197,94,${0.45 + 0.3 * glow})` : CARD.boxShadow, borderColor: state === 'correct' ? GREEN : CARD.borderColor ?? undefined, background: state === 'correct' ? 'rgba(20,83,45,0.9)' : CARD.background, borderWidth: state === 'correct' ? 5 : 2}}>
      <div style={{width: 84, height: 84, borderRadius: 20, background: state === 'correct' ? GREEN : ACCENT, color: '#0a1736', fontWeight: 800, fontSize: 56, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>{state === 'correct' ? '✓' : letter}</div>
      <div style={{color, fontWeight: 700, fontSize: text.length > 24 ? 44 : 52, lineHeight: 1.15}}>{text}</div>
    </div>
  );
};

/** Question and answer scenes share one layout: question on top, four option cards, the right one lights up. */
export const QuestionScene: React.FC<{scene: LongScene}> = ({scene}) => {
  const isAnswer = scene.kind === 'answer';
  const t = useSeconds();
  const revealed = isAnswer && t >= (scene.reveal_at ?? 0.9);
  const explain = useReveal(scene.explain_at ?? 2.2);
  const head = useReveal(0.1);
  return (
    <>
      <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH - 200, top: 196, fontFamily, opacity: head}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 36, marginBottom: 30}}>
          <div style={{color: ACCENT, fontWeight: 800, fontSize: 40}}>प्रश्न {devanagari(scene.q_index ?? 1)} / {devanagari(scene.total ?? 10)}</div>
          <QuizDots current={scene.q_index ?? 1} total={scene.total ?? 10} done={isAnswer} />
        </div>
        <div style={{color: COLORS.white, fontWeight: 800, fontSize: scene.headline.length <= 50 ? 70 : 60, lineHeight: 1.2, textShadow: '0 4px 22px rgba(0,0,0,0.55)'}}>{scene.headline}</div>
      </div>
      {isAnswer ? null : <Timer scene={scene} />}
      <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: 490, display: 'flex', flexWrap: 'wrap', gap: 28, justifyContent: 'space-between', fontFamily}}>
        {scene.items.map((item, i) => (
          <Option key={i} letter={item.value ?? ''} text={item.label} cue={isAnswer ? 0.05 : item.cue} state={!revealed ? 'idle' : i === scene.correct ? 'correct' : 'wrong'} />
        ))}
      </div>
      {isAnswer && scene.subtitle ? (
        <div style={{position: 'absolute', left: CONTENT_LEFT + 80, width: CONTENT_WIDTH - 160, top: 842, minHeight: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '14px 36px', boxSizing: 'border-box', borderRadius: 24, background: 'rgba(8,16,40,0.82)', border: '2px solid rgba(34,197,94,0.55)', fontFamily, color: COLORS.white, fontWeight: 700, fontSize: 42, lineHeight: 1.3, opacity: explain, textAlign: 'center', transform: `translateY(${(1 - explain) * 20}px)`}}>{scene.subtitle}</div>
      ) : null}
    </>
  );
};

export const QuizIntro: React.FC<{scene: LongScene}> = ({scene}) => <Big scene={scene} />;
export const QuizEnd: React.FC<{scene: LongScene}> = ({scene}) => <Big scene={scene} closing />;
