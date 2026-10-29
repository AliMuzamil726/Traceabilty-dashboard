/** Public entry of module 3. Other code imports this module only through this file. */
export { meta } from './module.meta';
export { default } from './pages/FieldbookPage';

/** Read-only fieldbook data the Register export needs: officers and their farmers. */
export { fieldbookApi, fieldbookKeys } from './api/client';
export type { FarmerOption, OfficerOption } from './api/types';
