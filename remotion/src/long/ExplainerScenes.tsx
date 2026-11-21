import React from 'react';
import {fontFamily} from '../fonts';
import {COLORS} from '../bulletin/constants';
import {LongItem, LongScene} from './types';
import {BODY_BOTTOM, BODY_TOP, CARD, CONTENT_LEFT, CONTENT_WIDTH, Headline, devanagari, useReveal, useSeconds} from './kit';

const LATIN = (text: string): string => text.replace(/[०-९]/g, (d) => String('०१२३४५६७८९'.indexOf(d)));

/** A figure that counts up to its value as it appears (years and non-numeric text stay still). Returns Devanagari digits. */
export const countUp = (value: string, t: number): string => {
  const m = LATIN(value).match(/^([^\d]*)([\d,]*\.?\d+)(.*)$/);
  if (!m || t >= 1) return value;
  const raw = m[2];
  const num = parseFloat(raw.replace(/,/g, ''));
  const isYear = !raw.includes(',') && !raw.includes('.') && num >= 1000 && num <= 2100 && !m[1] && !m[3].trim();
  if (!Number.isFinite(num) || isYear || num > 1e12) return value;
  const decimals = (raw.split('.')[1] || '').length;
  const eased = 1 - Math.pow(1 - Math.max(0, t), 3);
  const now = num * eased;
  const text = raw.includes(',') ? now.toLocaleString('en-IN', {minimumFractionDigits: decimals, maximumFractionDigits: decimals}) : now.toFixed(decimals);
  return (m[1] + text + m[3]).replace(/\d/g, (d) => '०१२३४५६७८९'[Number(d)]);
};

const rise = (p: number) => ({opacity: p, transform: `translateY(${(1 - p) * 34}px)`});

const Item: React.FC<{item: LongItem; render: (p: number) => React.ReactNode}> = ({item, render}) => {
  const p = useReveal(item.cue, 18);
  return <>{render(Math.min(1, Math.max(0, p)))}</>;
};

/** Cover scene: the hook line in huge type with a glowing ring. */
const Title: React.FC<{scene: LongScene}> = ({scene}) => {
  const p = useReveal(0.15);
  const t = useSeconds();
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '120px 140px 220px', fontFamily}}>
      <div style={{position: 'absolute', right: 130, top: 250, width: 430, height: 430, borderRadius: '50%', border: `10px solid ${COLORS.gold}`, opacity: 0.25 + 0.1 * Math.sin(t * 2), transform: `scale(${0.9 + 0.1 * p})`}} />
      <div style={{width: 220 * p, height: 14, background: COLORS.red, marginBottom: 30}} />
      <div style={{color: COLORS.white, fontWeight: 800, fontSize: scene.headline.length <= 34 ? 132 : 108, lineHeight: 1.18, maxWidth: 1450, ...rise(p), textShadow: '0 6px 30px rgba(0,0,0,0.6)'}}>{scene.headline}</div>
      {scene.subtitle ? <div style={{color: COLORS.gold, fontWeight: 700, fontSize: 56, marginTop: 28, maxWidth: 1450, opacity: useReveal(0.7)}}>{scene.subtitle}</div> : null}
    </div>
  );
};

const List: React.FC<{scene: LongScene; check?: boolean}> = ({scene, check}) => (
  <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: BODY_TOP, fontFamily, display: 'flex', flexDirection: 'column', gap: 18}}>
    {scene.items.map((item, i) => (
      <Item key={i} item={item} render={(p) => (
        <div style={{...CARD, ...rise(p), display: 'flex', alignItems: 'center', gap: 28, padding: '0 36px', height: 84, borderRadius: 22}}>
          <div style={{width: 50, height: 50, borderRadius: '50%', background: COLORS.gold, color: '#0a1736', fontWeight: 800, fontSize: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
            {check ? '✓' : devanagari(i + 1)}
          </div>
          <div style={{color: COLORS.white, fontWeight: 700, fontSize: 46, lineHeight: 1.2}}>{item.label}</div>
        </div>
      )} />
    ))}
  </div>
);

const Steps: React.FC<{scene: LongScene}> = ({scene}) => {
  const n = scene.items.length;
  const gap = 26;
  const width = (CONTENT_WIDTH - gap * (n - 1)) / n;
  return (
    <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: BODY_TOP + 10, fontFamily, display: 'flex', gap}}>
      {scene.items.map((item, i) => (
        <Item key={i} item={item} render={(p) => (
          <div style={{...CARD, ...rise(p), width, height: 330, padding: '28px 26px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 22}}>
            <div style={{width: 76, height: 76, borderRadius: '50%', background: COLORS.red, color: COLORS.white, fontWeight: 800, fontSize: 46, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{devanagari(i + 1)}</div>
            <div style={{color: COLORS.white, fontWeight: 700, fontSize: n >= 4 ? 38 : 44, lineHeight: 1.25}}>{item.label}</div>
          </div>
        )} />
      ))}
    </div>
  );
};

const Compare: React.FC<{scene: LongScene}> = ({scene}) => (
  <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: BODY_TOP, height: BODY_BOTTOM - BODY_TOP - 10, fontFamily, display: 'flex', gap: 60, alignItems: 'stretch'}}>
    {scene.items.map((item, i) => (
      <Item key={i} item={item} render={(p) => (
        <div style={{...CARD, ...rise(p), flex: 1, padding: '30px 38px', display: 'flex', flexDirection: 'column', gap: 18, borderColor: i === 0 ? 'rgba(34,211,238,0.6)' : 'rgba(245,196,81,0.55)'}}>
          <div style={{color: i === 0 ? '#22d3ee' : COLORS.gold, fontWeight: 800, fontSize: 54, lineHeight: 1.15}}>{item.label}</div>
          <div style={{color: COLORS.white, fontWeight: 600, fontSize: 44, lineHeight: 1.3}}>{item.value}</div>
        </div>
      )} />
    ))}
    <div style={{position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', width: 96, height: 96, borderRadius: '50%', background: COLORS.red, color: COLORS.white, fontWeight: 800, fontSize: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '5px solid #0a1736'}}>VS</div>
  </div>
);

const Timeline: React.FC<{scene: LongScene}> = ({scene}) => {
  const n = scene.items.length;
  const width = CONTENT_WIDTH / n;
  const line = Math.min(1, useReveal((scene.items[0]?.cue ?? 0.3) - 0.2));
  return (
    <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: BODY_TOP, height: 380, fontFamily}}>
      <div style={{position: 'absolute', left: 0, top: 132, height: 8, width: `${line * 100}%`, background: `linear-gradient(90deg, ${COLORS.gold}, #22d3ee)`, borderRadius: 4}} />
      {scene.items.map((item, i) => (
        <Item key={i} item={item} render={(p) => (
          <div style={{position: 'absolute', left: i * width, width: width - 16, top: 0, ...rise(p)}}>
            <div style={{color: COLORS.gold, fontWeight: 800, fontSize: 46, height: 100, display: 'flex', alignItems: 'flex-end', lineHeight: 1.15}}>{item.label}</div>
            <div style={{width: 34, height: 34, borderRadius: '50%', background: COLORS.red, border: '6px solid #fff', margin: '4px 0 18px', transform: `scale(${p})`}} />
            <div style={{color: COLORS.white, fontWeight: 600, fontSize: 38, lineHeight: 1.28}}>{item.value}</div>
          </div>
        )} />
      ))}
    </div>
  );
};

const Stat: React.FC<{scene: LongScene}> = ({scene}) => {
  const item = scene.items[0];
  const p = useReveal(item.cue, 14);
  const label = useReveal(item.cue + 0.35);
  const full = item.value ?? '';
  const counting = useSeconds() - item.cue;
  const value = countUp(full, counting / 1.1);
  return (
    <div style={{position: 'absolute', left: CONTENT_LEFT, width: CONTENT_WIDTH, top: BODY_TOP - 20, height: 400, fontFamily, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{color: COLORS.gold, fontWeight: 800, fontSize: full.length <= 8 ? 250 : full.length <= 14 ? 180 : 128, lineHeight: 1.05, opacity: p, transform: `scale(${0.7 + 0.3 * p})`, textShadow: '0 8px 40px rgba(245,196,81,0.35)'}}>{value}</div>
      <div style={{width: 640 * label, height: 8, background: COLORS.red, margin: '20px 0'}} />
      <div style={{color: COLORS.white, fontWeight: 700, fontSize: 54, opacity: label, textAlign: 'center'}}>{item.label}</div>
    </div>
  );
};

const Quote: React.FC<{scene: LongScene}> = ({scene}) => {
  const item = scene.items[0];
  const p = useReveal(item.cue, 18);
  const who = useReveal(item.cue + 0.8);
  return (
    <div style={{position: 'absolute', left: CONTENT_LEFT + 40, width: CONTENT_WIDTH - 80, top: BODY_TOP - 10, fontFamily}}>
      <div style={{color: COLORS.gold, fontSize: 170, lineHeight: 0.6, fontWeight: 800, opacity: p}}>“</div>
      <div style={{color: COLORS.white, fontWeight: 700, fontSize: 62, lineHeight: 1.3, ...rise(p)}}>{item.value}</div>
      <div style={{color: COLORS.gold, fontWeight: 800, fontSize: 44, marginTop: 24, opacity: who}}>— {item.label}</div>
    </div>
  );
};

/** One explainer scene: the headline in the header zone and the graphic for its kind in the body. */
export const ExplainerScene: React.FC<{scene: LongScene}> = ({scene}) => {
  if (scene.kind === 'title') return <Title scene={scene} />;
  return (
    <>
      <Headline text={scene.headline} subtitle={scene.subtitle} />
      {scene.kind === 'points' ? <List scene={scene} /> : null}
      {scene.kind === 'summary' ? <List scene={scene} check /> : null}
      {scene.kind === 'steps' ? <Steps scene={scene} /> : null}
      {scene.kind === 'compare' ? <Compare scene={scene} /> : null}
      {scene.kind === 'timeline' ? <Timeline scene={scene} /> : null}
      {scene.kind === 'stat' ? <Stat scene={scene} /> : null}
      {scene.kind === 'quote' ? <Quote scene={scene} /> : null}
    </>
  );
};
