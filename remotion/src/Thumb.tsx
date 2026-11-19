import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {fontFamily} from './fonts';
import {COLORS} from './bulletin/constants';

export type ThumbStyle = 'bold' | 'question' | 'figure' | 'alert';

export type ThumbProps = {
  /** The punchy line: at most about 5 words (a question or the hook), never the whole headline. */
  text: string;
  /** Red strip at the bottom-left (आजची क्विझ, समजून घ्या, ब्रेकिंग, आजच्या १० मोठ्या बातम्या). */
  tag?: string;
  /** The key figure, for example ₹१,२०० कोटी: the focal element of the 'figure' style. */
  figure?: string;
  photo?: {src: string} | null;
  style?: ThumbStyle;
  /** Hue rotation of the background so the variants (and the days) do not look alike. */
  hue?: number;
};

export const THUMB_W = 1280;
export const THUMB_H = 720;

const textSize = (t: string, width: 'wide' | 'narrow'): number => {
  const n = t.length;
  const base = n <= 12 ? 190 : n <= 20 ? 158 : n <= 28 ? 132 : 112;
  return width === 'wide' ? base : Math.round(base * 0.88);
};

/** The last one or two words in gold: one clear focus word, the rest white. */
const Words: React.FC<{text: string; size: number}> = ({text, size}) => {
  const words = text.split(' ').filter(Boolean);
  const gold = words.length > 3 ? 2 : 1;
  return (
    <div style={{fontWeight: 800, fontSize: size, lineHeight: 1.12, color: COLORS.white, textShadow: '0 6px 30px rgba(0,0,0,0.65)', textWrap: 'balance'} as React.CSSProperties}>
      {words.map((w, i) => (
        <span key={i} style={{color: i >= words.length - gold ? COLORS.gold : COLORS.white}}>
          {w}{' '}
        </span>
      ))}
    </div>
  );
};

const Tag: React.FC<{tag?: string}> = ({tag}) =>
  tag ? (
    <>
      <div style={{position: 'absolute', left: 0, bottom: 0, height: 112, padding: '0 54px', background: COLORS.red, color: COLORS.white, fontWeight: 800, fontSize: 62, display: 'flex', alignItems: 'center'}}>{tag}</div>
      <div style={{position: 'absolute', left: 0, bottom: 112, width: 820, height: 8, background: COLORS.gold}} />
    </>
  ) : null;

const Backdrop: React.FC<{hue: number; glowX?: string}> = ({hue, glowX = '25%'}) => (
  <AbsoluteFill style={{filter: hue ? `hue-rotate(${hue}deg)` : undefined}}>
    <AbsoluteFill style={{background: `linear-gradient(160deg, ${COLORS.bgTop} 0%, ${COLORS.bgBottom} 100%)`}} />
    <AbsoluteFill style={{background: `radial-gradient(760px 560px at ${glowX} 45%, rgba(40,90,220,0.42), transparent 70%)`}} />
  </AbsoluteFill>
);

const Logo: React.FC = () => <Img src={staticFile('logo.png')} style={{position: 'absolute', left: 40, top: 14, height: 128}} />;

/** Photo (or, with none, rings) behind a gold cut line on the right third. */
const RightVisual: React.FC<{photo?: {src: string} | null; figure?: string}> = ({photo, figure}) => (
  <>
    <div style={{position: 'absolute', right: 0, top: 0, width: 560, height: THUMB_H, clipPath: 'polygon(110px 0, 100% 0, 100% 100%, 0 100%)', background: '#0c1b40', overflow: 'hidden'}}>
      {photo ? <Img src={staticFile(photo.src)} style={{width: '100%', height: '100%', objectFit: 'cover'}} /> : null}
      {!photo ? (
        <>
          <div style={{position: 'absolute', left: 120, top: 110, width: 440, height: 440, borderRadius: '50%', border: `14px solid ${COLORS.gold}`, opacity: 0.5}} />
          <div style={{position: 'absolute', left: 190, top: 180, width: 300, height: 300, borderRadius: '50%', border: `10px solid ${COLORS.red}`, opacity: 0.7}} />
        </>
      ) : null}
      {!photo && figure ? (
        <div style={{position: 'absolute', inset: 0, paddingLeft: 90, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: COLORS.gold, fontWeight: 800, lineHeight: 1.08, fontSize: figure.length <= 6 ? 170 : figure.length <= 10 ? 118 : 88, textShadow: '0 6px 30px rgba(0,0,0,0.6)'}}>{figure}</div>
      ) : null}
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(5,10,22,0.55) 0%, rgba(5,10,22,0) 45%)'}} />
    </div>
    <svg style={{position: 'absolute', right: 0, top: 0}} width={560} height={THUMB_H}>
      <line x1={110} y1={0} x2={0} y2={THUMB_H} stroke={COLORS.gold} strokeWidth={9} />
    </svg>
  </>
);

const Bold: React.FC<ThumbProps> = ({text, tag, figure, photo, hue = 0}) => (
  <AbsoluteFill style={{fontFamily}}>
    <Backdrop hue={hue} />
    <RightVisual photo={photo} figure={figure} />
    <Logo />
    <div style={{position: 'absolute', left: 52, top: 150, width: 740, bottom: 150, display: 'flex', alignItems: 'center'}}>
      <Words text={text} size={textSize(text, 'narrow')} />
    </div>
    <Tag tag={tag} />
  </AbsoluteFill>
);

/** A giant gold question mark: the cheapest, strongest curiosity signal. */
const Question: React.FC<ThumbProps> = ({text, tag, hue = 0}) => (
  <AbsoluteFill style={{fontFamily}}>
    <Backdrop hue={hue} glowX="78%" />
    <div style={{position: 'absolute', right: 20, top: -60, fontSize: 760, fontWeight: 800, lineHeight: 1, color: COLORS.gold, textShadow: '0 0 90px rgba(245,196,81,0.5), 0 10px 40px rgba(0,0,0,0.6)', opacity: 0.95}}>?</div>
    <Logo />
    <div style={{position: 'absolute', left: 52, top: 150, width: 760, bottom: 150, display: 'flex', alignItems: 'center'}}>
      <Words text={text} size={textSize(text, 'narrow')} />
    </div>
    <Tag tag={tag} />
  </AbsoluteFill>
);

/** The key figure as the hero, the line under it. Falls back to Bold when the story has no figure. */
const Figure: React.FC<ThumbProps> = (props) => {
  const {text, tag, figure, hue = 0} = props;
  if (!figure) return <Bold {...props} />;
  return (
    <AbsoluteFill style={{fontFamily}}>
      <Backdrop hue={hue} glowX="50%" />
      <Logo />
      <div style={{position: 'absolute', left: 0, right: 0, top: 120, display: 'flex', justifyContent: 'center', color: COLORS.gold, fontWeight: 800, fontSize: figure.length <= 6 ? 330 : figure.length <= 10 ? 236 : 170, lineHeight: 1.05, textShadow: '0 0 70px rgba(245,196,81,0.45), 0 10px 40px rgba(0,0,0,0.6)'}}>{figure}</div>
      <div style={{position: 'absolute', left: 60, right: 60, bottom: 150, display: 'flex', justifyContent: 'center', textAlign: 'center'}}>
        <div style={{color: COLORS.white, fontWeight: 800, fontSize: Math.min(textSize(text, 'narrow'), 104), lineHeight: 1.15, textShadow: '0 4px 24px rgba(0,0,0,0.7)'}}>{text}</div>
      </div>
      <Tag tag={tag} />
    </AbsoluteFill>
  );
};

/** News-alert look: red stripes, each line of text on its own black plate. */
const Alert: React.FC<ThumbProps> = ({text, tag, photo, hue = 0}) => {
  const words = text.split(' ').filter(Boolean);
  const lines: string[] = [];
  for (let i = 0; i < words.length; i += 2) lines.push(words.slice(i, i + 2).join(' '));
  return (
    <AbsoluteFill style={{fontFamily, background: '#0b0b0f'}}>
      <AbsoluteFill style={{filter: hue ? `hue-rotate(${hue}deg)` : undefined, background: 'repeating-linear-gradient(115deg, #7f0f1c 0 70px, #4a0912 70px 140px)', opacity: 0.9}} />
      {photo ? <Img src={staticFile(photo.src)} style={{position: 'absolute', right: 0, top: 0, width: 520, height: THUMB_H, objectFit: 'cover', clipPath: 'polygon(90px 0, 100% 0, 100% 100%, 0 100%)'}} /> : null}
      <Logo />
      <div style={{position: 'absolute', left: 40, top: 150, display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'flex-start'}}>
        {lines.slice(0, 4).map((line, i) => (
          <div key={i} style={{background: i === lines.length - 1 ? COLORS.gold : '#000', color: i === lines.length - 1 ? '#111' : '#fff', fontWeight: 800, fontSize: textSize(text, 'narrow') * 0.92, lineHeight: 1.1, padding: '4px 30px 10px', transform: 'skewX(-8deg)', boxShadow: '0 10px 30px rgba(0,0,0,0.5)'}}>{line}</div>
        ))}
      </div>
      <Tag tag={tag} />
    </AbsoluteFill>
  );
};

export const MahaSparkThumbnail: React.FC<ThumbProps> = (props) => {
  switch (props.style) {
    case 'question':
      return <Question {...props} />;
    case 'figure':
      return <Figure {...props} />;
    case 'alert':
      return <Alert {...props} />;
    default:
      return <Bold {...props} />;
  }
};
