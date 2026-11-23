import React from 'react';
import {ThemeName} from '../types';
import {BreakingNewsStudio} from './BreakingNewsStudio';
import {DataTelemetryStudio} from './DataTelemetryStudio';
import {EditorialDeskLight} from './EditorialDeskLight';
import {GlassNewsroomDepth} from './GlassNewsroomDepth';
import {AuroraStudio} from './AuroraStudio';
import {OrbitStudio} from './OrbitStudio';
import {BlueprintStudio} from './BlueprintStudio';
import {ChalkboardStudio} from './ChalkboardStudio';
import {DataMapStudio} from './DataMapStudio';
import {PrimeGridStudio} from './PrimeGridStudio';

/** story.json's visual_theme selects which studio motion background is rendered. */
export const STUDIOS: Record<ThemeName, React.FC> = {
  PrimeGridStudio,
  BreakingNewsStudio,
  EditorialDeskLight,
  DataTelemetryStudio,
  GlassNewsroomDepth,
  ChalkboardStudio,
  BlueprintStudio,
  DataMapStudio,
  AuroraStudio,
  OrbitStudio,
};

export const getStudio = (theme: string): React.FC =>
  (STUDIOS as Record<string, React.FC>)[theme] ?? PrimeGridStudio;
