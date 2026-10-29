import type { IconDefinition } from "@fortawesome/fontawesome-svg-core";
import {
  faBolt,
  faClockRotateLeft,
  faCrown,
  faFireFlameCurved,
  faGamepad,
  faGhost,
  faHouse,
  faShapes,
  faStar,
  faToolbox,
  faTrophy,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";

/** Individually imported, licensed library icons keep the directory's solid silhouette. */
export const catalogIcons = {
  home: faHouse,
  recent: faClockRotateLeft,
  latest: faBolt,
  hot: faFireFlameCurved,
  site: faGamepad,
  wanted: faStar,
  authors: faCrown,
  contributors: faTrophy,
  categories: faShapes,
  game: faGamepad,
  circle: faGhost,
  tools: faToolbox,
  close: faXmark,
} satisfies Record<string, IconDefinition>;

export type CatalogIconName = keyof typeof catalogIcons;
