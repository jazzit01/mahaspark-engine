import React from 'react';
import {AbsoluteFill, Video, staticFile} from 'remotion';

/** An optional looping background clip (for example made with lemo-opuscar, kept in public/loops/): muted, looped,
 * under a dark scrim so the graphics and captions stay readable. Scenes with a topic photo cover it. */
export const LoopBackdrop: React.FC<{file: string}> = ({file}) => (
  <AbsoluteFill>
    <Video src={staticFile(file)} loop muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
    <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(3,6,16,0.78) 0%, rgba(3,6,16,0.6) 50%, rgba(3,6,16,0.82) 100%)'}} />
  </AbsoluteFill>
);
