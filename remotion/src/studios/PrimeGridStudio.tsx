import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

const GRID_MASK = 'linear-gradient(to top, rgba(0,0,0,1) 12%, rgba(0,0,0,0) 96%)';

const Rule: React.FC<{y: number; progress: number}> = ({y, progress}) => (
  <div
    style={{
      position: 'absolute',
      left: 60,
      right: 60,
      top: y,
      height: 3,
      transformOrigin: 'left center',
      transform: `scaleX(${progress})`,
      background:
        'linear-gradient(90deg, #F5C451 0%, #F5C451 16%, rgba(34,211,238,0.95) 16%, rgba(34,211,238,0.12) 100%)',
    }}
  />
);

/** Deep broadcast navy with a 3D-perspective drifting coordinate grid, light sweeps and gold/cyan rules. */
export const PrimeGridStudio: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const fineShift = (t * 96) % 120;
  const boldShift = (t * 96) % 480;
  const sweepA = interpolate((t % 7) / 7, [0, 1], [-800, 1500]);
  const sweepB = interpolate(((t + 3.5) % 9) / 9, [0, 1], [1500, -800]);
  const draw = interpolate(frame, [0, 26], [0, 1], {extrapolateRight: 'clamp'});
  const glow = 0.55 + 0.15 * Math.sin(t * 0.9);

  // Floor plane: the container owns the perspective so the horizon sits ABOVE the floor; each grid
  // layer is a tall plane pivoting on the container's bottom edge and receding toward the horizon.
  const floor: React.CSSProperties = {
    position: 'absolute',
    left: -1300,
    right: -1300,
    bottom: 0,
    height: 3200,
    transformOrigin: '50% 100%',
    transform: 'rotateX(72deg)',
  };

  return (
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #0B1526 0%, #080E1A 48%, #050912 100%)'}}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 0,
          height: 1100,
          background: `radial-gradient(ellipse at 50% 0%, rgba(34,211,238,${0.16 * glow}) 0%, transparent 62%)`,
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 960,
          bottom: 0,
          perspective: 760,
          perspectiveOrigin: '50% -25%',
          WebkitMaskImage: GRID_MASK,
          maskImage: GRID_MASK,
        }}
      >
        <div
          style={{
            ...floor,
            backgroundImage:
              'linear-gradient(rgba(34,211,238,0.45) 3px, transparent 3px), linear-gradient(90deg, rgba(34,211,238,0.36) 3px, transparent 3px)',
            backgroundSize: '120px 120px',
            backgroundPosition: `0px ${fineShift}px`,
          }}
        />
        <div
          style={{
            ...floor,
            backgroundImage:
              'linear-gradient(rgba(245,196,81,0.65) 5px, transparent 5px), linear-gradient(90deg, rgba(245,196,81,0.5) 5px, transparent 5px)',
            backgroundSize: '480px 480px',
            backgroundPosition: `0px ${boldShift}px`,
          }}
        />
      </div>

      <div
        style={{
          position: 'absolute',
          top: -300,
          left: sweepA,
          width: 380,
          height: 2600,
          transform: 'rotate(16deg)',
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.075), transparent)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: -300,
          left: sweepB,
          width: 240,
          height: 2600,
          transform: 'rotate(16deg)',
          background: 'linear-gradient(90deg, transparent, rgba(34,211,238,0.07), transparent)',
        }}
      />

      <Rule y={262} progress={draw} />
      <Rule y={1498} progress={draw} />
      <div style={{position: 'absolute', left: 60, top: 252, width: 14, height: 14, background: '#F5C451', opacity: draw}} />
      <div style={{position: 'absolute', right: 60, top: 1488, width: 14, height: 14, background: '#22D3EE', opacity: draw}} />

      <AbsoluteFill
        style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.55) 100%)'}}
      />
    </AbsoluteFill>
  );
};
