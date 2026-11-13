import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {fontFamily} from './fonts';
import {Palette} from './theme';

type Props = {
  category: string;
  palette: Palette;
};

/**
 * Locked brand layer, rendered once on its own top-level <AbsoluteFill> ABOVE every scene so the
 * logo and category pill stay 100% steady across scene cuts: no animation, no Sequence, no props
 * that change over time.
 *
 * Rules: only the MahaSpark logo file (no extra brand text), and no date/time badge of any kind.
 */
export const SharedOverlay: React.FC<Props> = ({category, palette}) => {
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: 34,
          top: 34,
          width: 300,
          height: 200,
          borderRadius: 22,
          background: palette.logoPlate ?? 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Img
          src={staticFile('logo.png')}
          style={{width: 300, height: 200, objectFit: 'contain', display: 'block'}}
        />
      </div>

      <div
        style={{
          position: 'absolute',
          right: 54,
          top: 112,
          padding: '10px 30px 14px',
          background: palette.pillBackground,
          color: palette.pillText,
          fontFamily,
          fontWeight: 800,
          fontSize: 38,
          lineHeight: 1.2,
          borderRadius: 10,
          letterSpacing: 0.2,
          boxShadow: '0 6px 22px rgba(0,0,0,0.35)',
          border: '1px solid rgba(255,255,255,0.28)',
          whiteSpace: 'nowrap',
        }}
      >
        {category}
      </div>
    </AbsoluteFill>
  );
};
