import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS} from './constants';
import {BulletinPhoto} from './types';

export type ThumbnailProps = {
  headline: string;
  /** Bulletin: shows "आजच्या N मोठ्या बातम्या". */
  count?: number;
  /** Single video: a short red tag (ताजी बातमी, ब्रेकिंग) instead of the count. */
  tag?: string;
  /** The story's key figure (for example ₹१,२०० कोटी), shown in gold on the panel when there is no photo. */
  figure?: string;
  photo?: BulletinPhoto | null;
};

export const THUMB_WIDTH = 1280;
export const THUMB_HEIGHT = 720;

/** YouTube thumbnail (1280x720): the top story in huge type, photo behind a gold cut line, red "N big news" tag. */
export const BulletinThumbnail: React.FC<ThumbnailProps> = ({headline, count, tag, figure, photo}) => {
  const size = headline.length <= 24 ? 112 : headline.length <= 36 ? 96 : 82;
  return (
    <AbsoluteFill style={{background: `linear-gradient(160deg, ${COLORS.bgTop} 0%, ${COLORS.bgBottom} 100%)`, fontFamily}}>
      <AbsoluteFill style={{background: 'radial-gradient(700px 520px at 25% 45%, rgba(40,90,220,0.35), transparent 70%)'}} />
      <div style={{position: 'absolute', right: 0, top: 0, width: 600, height: THUMB_HEIGHT, clipPath: 'polygon(110px 0, 100% 0, 100% 100%, 0 100%)', background: '#0c1b40', overflow: 'hidden'}}>
        {photo ? <Img src={staticFile(photo.src)} style={{width: '100%', height: '100%', objectFit: 'cover'}} /> : null}
        {!photo && figure ? (
          <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', paddingLeft: 90, color: COLORS.gold, fontWeight: 800, fontSize: figure.length <= 6 ? 190 : figure.length <= 10 ? 130 : 96, textShadow: '0 6px 30px rgba(0,0,0,0.55)', textAlign: 'center', lineHeight: 1.1}}>
            {figure}
          </div>
        ) : null}
        <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(5,10,22,0.6) 0%, rgba(5,10,22,0) 45%)'}} />
      </div>
      <svg style={{position: 'absolute', right: 0, top: 0}} width={600} height={THUMB_HEIGHT}>
        <line x1={110} y1={0} x2={0} y2={THUMB_HEIGHT} stroke={COLORS.gold} strokeWidth={9} />
      </svg>
      <Img src={staticFile('logo.png')} style={{position: 'absolute', left: 40, top: 14, height: 150}} />
      <div style={{position: 'absolute', left: 48, top: 170, width: 700, bottom: 150, display: 'flex', alignItems: 'center'}}>
        <div style={{color: COLORS.white, fontWeight: 800, fontSize: size, lineHeight: 1.2, textShadow: '0 4px 24px rgba(0,0,0,0.5)', textWrap: 'balance'} as React.CSSProperties}>
          {headline}
        </div>
      </div>
      <div style={{position: 'absolute', left: 0, bottom: 0, height: 118, padding: '0 56px', background: COLORS.red, color: COLORS.white, fontWeight: 800, fontSize: 64, display: 'flex', alignItems: 'center'}}>
        {tag ?? `आजच्या ${count ?? 10} मोठ्या बातम्या`}
      </div>
      <div style={{position: 'absolute', left: 0, bottom: 118, width: 880, height: 8, background: COLORS.gold}} />
    </AbsoluteFill>
  );
};
