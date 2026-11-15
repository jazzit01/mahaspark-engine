import React from 'react';
import {useCurrentFrame} from 'remotion';
import {fontFamily} from '../fonts';
import {COLORS, TICKER_HEIGHT} from './constants';

const LABEL_WIDTH = 360;
const PX_PER_FRAME = 3;

/** Bottom news ticker: red label, the following headlines scrolling left, and a thin bulletin progress line on top. */
export const Ticker: React.FC<{headlines: string[]; label: string; offset: number; total: number}> = ({headlines, label, offset, total}) => {
  const frame = useCurrentFrame();
  const progress = (offset + frame) / total;
  const line = headlines.join('   ◆   ');
  const text = `${line}   ◆   ${line}`;
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: TICKER_HEIGHT, background: COLORS.ticker}}>
      <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 6, background: COLORS.red}}>
        <div style={{width: `${Math.min(1, Math.max(0, progress)) * 100}%`, height: '100%', background: COLORS.gold}} />
      </div>
      <div style={{position: 'absolute', left: LABEL_WIDTH, right: 0, top: 6, bottom: 0, overflow: 'hidden'}}>
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            whiteSpace: 'nowrap',
            fontFamily,
            fontWeight: 700,
            fontSize: 42,
            color: COLORS.white,
            transform: `translateX(${40 - frame * PX_PER_FRAME}px)`,
          }}
        >
          {text}
        </div>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 6,
          bottom: 0,
          width: LABEL_WIDTH,
          background: COLORS.red,
          color: COLORS.white,
          fontFamily,
          fontWeight: 800,
          fontSize: 40,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {label}
      </div>
    </div>
  );
};
