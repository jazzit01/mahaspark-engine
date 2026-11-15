import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS, PHOTO_CUT, PHOTO_WIDTH, TEXT_LEFT, TEXT_WIDTH, TICKER_HEIGHT, TRANSITION_FRAMES, headlineSize} from './constants';
import {BulletinItem} from './types';

const PANEL_HEIGHT = 1080 - TICKER_HEIGHT;
const CUT_CLIP = `polygon(${PHOTO_CUT}px 0, 100% 0, 100% 100%, 0 100%)`;

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 90) * 40;
  return (
    <AbsoluteFill style={{background: `linear-gradient(160deg, ${COLORS.bgTop} 0%, ${COLORS.bgBottom} 100%)`}}>
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${COLORS.grid} 2px, transparent 2px), linear-gradient(90deg, ${COLORS.grid} 2px, transparent 2px)`,
          backgroundSize: '96px 96px',
          backgroundPosition: `${drift}px 0`,
        }}
      />
      <AbsoluteFill style={{background: 'radial-gradient(900px 700px at 25% 40%, rgba(40,90,220,0.28), transparent 70%)'}} />
    </AbsoluteFill>
  );
};

/** Photo (Ken Burns) behind a diagonal gold cut line, or animated rings when no photo exists. */
const Panel: React.FC<{item: BulletinItem; total: number}> = ({item, total}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const slide = spring({frame: frame - 4, fps, config: {damping: 200, mass: 0.9}});
  const x = interpolate(slide, [0, 1], [PHOTO_WIDTH, 0]);
  const zoom = interpolate(frame, [0, total], [1.06, 1.2], {easing: Easing.inOut(Easing.quad), extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: 1920 - PHOTO_WIDTH, top: 0, width: PHOTO_WIDTH, height: PANEL_HEIGHT, transform: `translateX(${x}px)`}}>
      <div style={{position: 'absolute', inset: 0, clipPath: CUT_CLIP, overflow: 'hidden', background: '#0c1b40'}}>
        {item.photo ? (
          <>
            <Img
              src={staticFile(item.photo.src)}
              style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom})`, transformOrigin: '60% 45%'}}
            />
            <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(5,10,22,0.55) 0%, rgba(5,10,22,0) 40%)'}} />
          </>
        ) : (
          <svg width="100%" height="100%" viewBox={`0 0 ${PHOTO_WIDTH} ${PANEL_HEIGHT}`}>
            {[0, 1, 2, 3, 4].map((i) => {
              const r = 140 + i * 130 + Math.sin(frame / 40 + i) * 14;
              return <circle key={i} cx={560} cy={PANEL_HEIGHT / 2} r={r} fill="none" stroke={i % 2 ? COLORS.gold : '#3b6cff'} strokeOpacity={0.35 - i * 0.05} strokeWidth={4} />;
            })}
            <circle cx={560} cy={PANEL_HEIGHT / 2} r={46} fill={COLORS.red} />
          </svg>
        )}
      </div>
      <svg style={{position: 'absolute', inset: 0}} width={PHOTO_WIDTH} height={PANEL_HEIGHT}>
        <line x1={PHOTO_CUT} y1={0} x2={0} y2={PANEL_HEIGHT} stroke={COLORS.gold} strokeWidth={8} />
      </svg>
    </div>
  );
};

export const ItemScreen: React.FC<{item: BulletinItem; frames: number}> = ({item, frames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = (delay: number) => spring({frame: frame - delay, fps, config: {damping: 200, mass: 0.7}});
  const bar = enter(2);
  const head = enter(6);
  const ctx = enter(16);
  const size = headlineSize(item.headline);

  // wipe on every cut: a red then navy sweep across the full frame
  const wipe = interpolate(frame, [0, TRANSITION_FRAMES], [0, 1], {extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});

  return (
    <AbsoluteFill>
      <Background />
      <Panel item={item} total={frames} />
      <div
        style={{
          position: 'absolute',
          left: TEXT_LEFT,
          top: 190,
          width: TEXT_WIDTH,
          height: 1080 - TICKER_HEIGHT - 190 - 40,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          fontFamily,
        }}
      >
        <div style={{width: 160 * bar, height: 16, background: COLORS.red, marginBottom: 34}} />
        <div
          style={{
            color: COLORS.white,
            fontWeight: 800,
            fontSize: size,
            lineHeight: 1.22,
            textWrap: 'balance',
            textShadow: '0 4px 24px rgba(0,0,0,0.45)',
            opacity: head,
            transform: `translateX(${(1 - head) * -80}px)`,
          } as React.CSSProperties}
        >
          {item.headline}
        </div>
        <div
          style={{
            marginTop: 30,
            color: COLORS.context,
            fontWeight: 600,
            fontSize: 48,
            lineHeight: 1.4,
            opacity: ctx,
            transform: `translateY(${(1 - ctx) * 30}px)`,
          }}
        >
          {item.context}
        </div>
      </div>
      {wipe < 1 && (
        <>
          <AbsoluteFill style={{background: COLORS.red, transform: `translateX(${(wipe * 2 - 1) * 100}%)`}} />
          <AbsoluteFill style={{background: COLORS.bgBottom, transform: `translateX(${(wipe * 2 - 1.25) * 100}%)`}} />
        </>
      )}
    </AbsoluteFill>
  );
};
