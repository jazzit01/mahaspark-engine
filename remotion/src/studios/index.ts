import React from 'react';
import {ThemeName} from '../types';
import {BreakingNewsStudio} from './BreakingNewsStudio';
import {DataTelemetryStudio} from './DataTelemetryStudio';
import {EditorialDeskLight} from './EditorialDeskLight';
import {GlassNewsroomDepth} from './GlassNewsroomDepth';
import {PrimeGridStudio} from './PrimeGridStudio';

/** story.json's visual_theme selects which studio motion background is rendered. */
export const STUDIOS: Record<ThemeName, React.FC> = {
  PrimeGridStudio,
  BreakingNewsStudio,
  EditorialDeskLight,
  DataTelemetryStudio,
  GlassNewsroomDepth,
};

export const getStudio = (theme: string): React.FC =>
  (STUDIOS as Record<string, React.FC>)[theme] ?? PrimeGridStudio;
