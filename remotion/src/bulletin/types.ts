export type BulletinPhoto = {
  src: string; // path inside remotion/public
  width: number;
  height: number;
  credit: string;
  is_figure: boolean;
};

export type BulletinItem = {
  category: string; // metadata only: never drawn on screen
  headline: string;
  context: string;
  audio: string; // path inside remotion/public
  seconds: number;
  start: number;
  lead_seconds: number;
  photo?: BulletinPhoto | null;
  highlight?: string; // key figure for the no-photo panel
};

export type BulletinProps = {
  items: BulletinItem[];
  outro_seconds: number;
  outro_start: number;
  total_seconds: number;
  credits: string[];
};
