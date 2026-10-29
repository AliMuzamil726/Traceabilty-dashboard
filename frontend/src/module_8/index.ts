/** Public entry of module 8. Other code imports this module only through this file. */
export { meta } from './module.meta';
export { default } from './pages/SettingsLayout';

/**
 * The configuration every screen needs before it draws: map tiles and their
 * attribution, the QR base URL, the season label. Exported so Modules 1, 2, 4 and 7
 * read one source rather than each carrying its own copy.
 */
export { useAppConfig, useMapConfig, FALLBACK_TILES } from './hooks/useAppConfig';
export { usePreferences } from './hooks/useSettings';
export type { PublicConfig, TileLayer, Preferences } from './api/types';

/** Staff and administrator lists the Register export offers. */
export { settingsApi, settingsKeys } from './api/client';
export type { Officer } from './api/types';
