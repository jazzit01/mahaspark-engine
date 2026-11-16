import React, {useMemo} from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {CAPTION_SIZE, HEIGHT, SAFE_BOTTOM, SAFE_SIDE} from './constants';
import {fontFamily} from './fonts';
import {Palette} from './theme';
import {StoryWord} from './types';

type Chunk = {words: StoryWord[]; start: number; end: number};

const MAX_WORDS_PER_CHUNK = 5;
const BREAK_AFTER = /[.,]$/;

/** Split the spoken words into short caption lines, never crossing a scene boundary. */
export const buildChunks = (words: StoryWord[]): Chunk[] => {
  const chunks: Chunk[] = [];
  let current: StoryWord[] = [];

  const flush = () => {
    if (current.length > 0) {
      chunks.push({words: current, start: current[0].start, end: current[current.length - 1].end});
      current = [];
    }
  };

  words.forEach((word, i) => {
    if (current.length > 0 && current[0].scene !== word.scene) {
      flush();
    }
    current.push(word);
    const sentenceEnd = /[.]$/.test(word.text);
    const softBreak = BREAK_AFTER.test(word.text) && current.length >= 3;
    if (current.length >= MAX_WORDS_PER_CHUNK || sentenceEnd || softBreak) {
      flush();
    }
    if (i === words.length - 1) {
      flush();
    }
  });
  return chunks;
};

const stripPunctuation = (text: string) => text.replace(/[.,]+$/, '');

type Props = {
  words: StoryWord[];
  palette: Palette;
};

/** Word-by-word karaoke captions synced to story.words; the active word is highlighted and lifted. */
export const Captions: React.FC<Props> = ({words, palette}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const chunks = useMemo(() => buildChunks(words), [words]);

  // The visible chunk is the last one that has started; it stays until the next one begins.
  let index = -1;
  for (let i = 0; i < chunks.length; i++) {
    if (t >= chunks[i].start - 0.05) {
      index = i;
    } else {
      break;
    }
  }
  const chunk = index >= 0 ? chunks[index] : null;
  const lastEnd = chunks.length > 0 ? chunks[chunks.length - 1].end : 0;
  if (!chunk || t > lastEnd + 0.4) {
    return null;
  }

  const chunkFrame = frame - Math.round(chunk.start * fps);
  const fadeIn = interpolate(chunkFrame, [-2, 4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <div
      style={{
        position: 'absolute',
        left: SAFE_SIDE,
        right: SAFE_SIDE,
        bottom: SAFE_BOTTOM + 8,
        display: 'flex',
        justifyContent: 'center',
        opacity: fadeIn,
        fontFamily,
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          columnGap: 18,
          rowGap: 6,
          padding: '18px 34px 22px',
          borderRadius: 24,
          background: palette.captionPlate,
          border: `1px solid ${palette.cardBorder}`,
          boxShadow: palette.isLight ? '0 10px 30px rgba(15,23,42,0.16)' : '0 10px 34px rgba(0,0,0,0.4)',
          maxWidth: 1500,
        }}
      >
        {chunk.words.map((word, i) => {
          const active = t >= word.start && t < word.end;
          const spoken = t >= word.end;
          const color = active ? palette.captionActive : spoken ? palette.captionSpoken : palette.captionUpcoming;
          const lift = active ? 1.08 : 1;
          return (
            <span
              key={`${index}-${i}`}
              style={{
                color,
                fontSize: CAPTION_SIZE,
                fontWeight: active ? 800 : 700,
                lineHeight: 1.35,
                transform: `scale(${lift})`,
                display: 'inline-block',
                textShadow: palette.isLight ? 'none' : '0 2px 10px rgba(0,0,0,0.55)',
              }}
            >
              {stripPunctuation(word.text)}
            </span>
          );
        })}
      </div>
    </div>
  );
};
