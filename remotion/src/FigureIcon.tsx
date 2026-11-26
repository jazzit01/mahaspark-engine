import React from 'react';
import {interpolate} from 'remotion';

type Props = {
  icon?: string;
  /** Local frame since the graphic appeared. */
  local: number;
  color: string;
  color2: string;
  /** 0-100, only used by the percent ring. */
  percent?: number;
  size?: number;
};

/** Draws a stroke from nothing: every path uses pathLength=1, so one dash value works for any shape. */
const draw = (local: number, from: number, to: number) => interpolate(local, [from, to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

/** Original line icons for a key figure (money, people, road, water, power, health, farming, buildings, percent ring
 *  and a generic burst). Plain SVG paths drawn in with the figure; no assets, no licence. */
export const FigureIcon: React.FC<Props> = ({icon = 'burst', local, color, color2, percent = 0, size = 150}) => {
  const line = {stroke: color, strokeWidth: 5, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, pathLength: 1, strokeDasharray: 1};
  const d1 = draw(local, 0, 26);
  const d2 = draw(local, 10, 36);
  const pop = interpolate(local, [0, 14], [0.6, 1], {extrapolateRight: 'clamp'});
  let body: React.ReactNode;
  switch (icon) {
    case 'percent': {
      const C = 2 * Math.PI * 38;
      const fill = (Math.min(Math.max(percent, 0), 100) / 100) * interpolate(local, [0, 42], [0, 1], {extrapolateRight: 'clamp'});
      body = (
        <>
          <circle cx="50" cy="50" r="38" stroke={color2} strokeOpacity={0.3} strokeWidth={9} fill="none" />
          <circle cx="50" cy="50" r="38" stroke={color} strokeWidth={9} fill="none" strokeLinecap="round" strokeDasharray={`${C * fill} ${C}`} transform="rotate(-90 50 50)" />
        </>
      );
      break;
    }
    case 'rupee':
      body = (
        <>
          <circle cx="50" cy="50" r="40" {...line} strokeDashoffset={d1} />
          <path d="M34 34 H66 M34 44 H66 M34 34 H44 C56 34 60 40 58 46 C56 52 48 54 40 54 L62 70" {...line} strokeDashoffset={d2} />
        </>
      );
      break;
    case 'people':
      body = (
        <>
          <circle cx="50" cy="30" r="11" {...line} strokeDashoffset={d1} />
          <path d="M30 70 C30 52 70 52 70 70 Z" {...line} strokeDashoffset={d1} />
          <circle cx="22" cy="40" r="8" {...line} strokeDashoffset={d2} strokeOpacity={0.7} />
          <circle cx="78" cy="40" r="8" {...line} strokeDashoffset={d2} strokeOpacity={0.7} />
          <path d="M8 74 C8 60 34 58 36 62 M92 74 C92 60 66 58 64 62" {...line} strokeDashoffset={d2} strokeOpacity={0.7} />
        </>
      );
      break;
    case 'road':
      body = (
        <>
          <path d="M42 12 L18 90 M58 12 L82 90" {...line} strokeDashoffset={d1} />
          <path d="M50 18 V30 M50 40 V56 M50 66 V86" {...line} stroke={color2} strokeDashoffset={d2} />
        </>
      );
      break;
    case 'drop':
      body = <path d="M50 10 C50 10 20 44 20 62 C20 80 34 90 50 90 C66 90 80 80 80 62 C80 44 50 10 50 10 Z M38 64 C38 72 44 76 50 76" {...line} strokeDashoffset={d1} />;
      break;
    case 'bolt':
      body = <path d="M58 8 L26 54 H48 L40 92 L76 42 H54 Z" {...line} strokeDashoffset={d1} />;
      break;
    case 'cross':
      body = (
        <>
          <circle cx="50" cy="50" r="40" {...line} strokeDashoffset={d1} />
          <path d="M50 28 V72 M28 50 H72" {...line} stroke={color2} strokeWidth={9} strokeDashoffset={d2} />
        </>
      );
      break;
    case 'wheat':
      body = (
        <>
          <path d="M50 92 V22" {...line} strokeDashoffset={d1} />
          <path d="M50 30 C38 28 32 18 34 8 C46 10 52 20 50 30 Z M50 30 C62 28 68 18 66 8 C54 10 48 20 50 30 Z M50 54 C38 52 30 42 32 32 C44 34 52 44 50 54 Z M50 54 C62 52 70 42 68 32 C56 34 48 44 50 54 Z" {...line} strokeDashoffset={d2} />
        </>
      );
      break;
    case 'building':
      body = (
        <>
          <path d="M18 90 V36 H54 V90 M54 56 H82 V90 M12 90 H88" {...line} strokeDashoffset={d1} />
          <path d="M28 48 H44 M28 62 H44 M28 76 H44 M64 68 H72 M64 78 H72" {...line} stroke={color2} strokeDashoffset={d2} />
        </>
      );
      break;
    default:
      body = (
        <>
          <circle cx="50" cy="50" r="14" {...line} strokeDashoffset={d1} />
          <path d="M50 8 V24 M50 76 V92 M8 50 H24 M76 50 H92 M20 20 L31 31 M69 69 L80 80 M80 20 L69 31 M31 69 L20 80" {...line} stroke={color2} strokeDashoffset={d2} />
        </>
      );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" style={{flexShrink: 0, transform: `scale(${pop})`, overflow: 'visible'}}>
      {body}
    </svg>
  );
};
