import {ThemeName} from './types';

export type Palette = {
  isLight: boolean;
  background: string;
  textPrimary: string;
  textSecondary: string;
  accent: string;
  accent2: string;
  cardBackground: string;
  cardBorder: string;
  /** backdrop-filter blur radius in px; 0 disables frosted glass. */
  cardBlur: number;
  pillBackground: string;
  pillText: string;
  captionActive: string;
  captionSpoken: string;
  captionUpcoming: string;
  captionPlate: string;
  textShadow: string;
  /** Dark plate behind the (white) MahaSpark logo on light studios; null on dark studios. */
  logoPlate: string | null;
};

const darkShadow = '0 3px 14px rgba(0,0,0,0.65)';

export const PALETTES: Record<ThemeName, Palette> = {
  PrimeGridStudio: {
    isLight: false,
    background: '#080E1A',
    textPrimary: '#F8FAFC',
    textSecondary: '#E2E8F0',
    accent: '#F5C451',
    accent2: '#22D3EE',
    cardBackground: 'rgba(8,14,26,0.80)',
    cardBorder: 'rgba(245,196,81,0.45)',
    cardBlur: 0,
    pillBackground: '#D90429',
    pillText: '#FFFFFF',
    captionActive: '#F5C451',
    captionSpoken: '#F8FAFC',
    captionUpcoming: 'rgba(248,250,252,0.55)',
    captionPlate: 'rgba(8,14,26,0.72)',
    textShadow: darkShadow,
    logoPlate: null,
  },
  BreakingNewsStudio: {
    isLight: false,
    background: '#0B0B0F',
    textPrimary: '#FFFFFF',
    textSecondary: '#F1F5F9',
    accent: '#F43F5E',
    accent2: '#F59E0B',
    cardBackground: 'rgba(14,14,20,0.84)',
    cardBorder: 'rgba(244,63,94,0.55)',
    cardBlur: 0,
    pillBackground: '#E11D48',
    pillText: '#FFFFFF',
    captionActive: '#FBBF24',
    captionSpoken: '#FFFFFF',
    captionUpcoming: 'rgba(255,255,255,0.55)',
    captionPlate: 'rgba(11,11,15,0.78)',
    textShadow: darkShadow,
    logoPlate: null,
  },
  EditorialDeskLight: {
    isLight: true,
    background: '#F8FAFC',
    textPrimary: '#0F172A',
    textSecondary: '#1E293B',
    accent: '#D90429',
    accent2: '#0F172A',
    cardBackground: 'rgba(255,255,255,0.92)',
    cardBorder: 'rgba(15,23,42,0.16)',
    cardBlur: 0,
    pillBackground: '#D90429',
    pillText: '#FFFFFF',
    captionActive: '#D90429',
    captionSpoken: '#0F172A',
    captionUpcoming: 'rgba(15,23,42,0.45)',
    captionPlate: 'rgba(255,255,255,0.88)',
    textShadow: 'none',
    logoPlate: '#0F172A',
  },
  DataTelemetryStudio: {
    isLight: false,
    background: '#050B1F',
    textPrimary: '#F8FAFC',
    textSecondary: '#E2E8F0',
    accent: '#10B981',
    accent2: '#FBBF24',
    cardBackground: 'rgba(5,11,31,0.82)',
    cardBorder: 'rgba(16,185,129,0.5)',
    cardBlur: 0,
    pillBackground: '#D90429',
    pillText: '#FFFFFF',
    captionActive: '#FBBF24',
    captionSpoken: '#F8FAFC',
    captionUpcoming: 'rgba(248,250,252,0.55)',
    captionPlate: 'rgba(5,11,31,0.74)',
    textShadow: darkShadow,
    logoPlate: null,
  },
  GlassNewsroomDepth: {
    isLight: false,
    background: '#0E1230',
    textPrimary: '#FFFFFF',
    textSecondary: '#F1F5F9',
    accent: '#7DD3FC',
    accent2: '#FBBF24',
    cardBackground: 'rgba(255,255,255,0.12)',
    cardBorder: 'rgba(255,255,255,0.28)',
    cardBlur: 28,
    pillBackground: '#D90429',
    pillText: '#FFFFFF',
    captionActive: '#FBBF24',
    captionSpoken: '#FFFFFF',
    captionUpcoming: 'rgba(255,255,255,0.55)',
    captionPlate: 'rgba(14,18,48,0.62)',
    textShadow: darkShadow,
    logoPlate: null,
  },
};

export const THEME_NAMES = Object.keys(PALETTES) as ThemeName[];

export const getPalette = (theme: string): Palette =>
  (PALETTES as Record<string, Palette>)[theme] ?? PALETTES.PrimeGridStudio;
