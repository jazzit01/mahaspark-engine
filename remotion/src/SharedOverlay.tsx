import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {Palette} from './theme';

type Props = {
  palette: Palette;
};

/**
 * Locked brand layer, rendered once on its own top-level <AbsoluteFill> ABOVE every scene so the
 * logo stays 100% steady across scene cuts: no animation, no Sequence, no props
 * that change over time.
 *
 * Rules: only the MahaSpark logo file (no extra brand text, no category pill), and no date/time badge of any kind.
 */
export const SharedOverlay: React.FC<Props> = ({palette}) => {
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: 40,
          top: 26,
          width: 230,
          height: 140,
          borderRadius: 22,
          background: palette.logoPlate ?? 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Img
          src={staticFile('logo.png')}
          style={{width: 230, height: 140, objectFit: 'contain', display: 'block'}}
        />
      </div>
    </AbsoluteFill>
  );
};
