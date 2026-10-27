/** Public entry of module 7. Other code imports this module only through this file. */
export { meta } from './module.meta';
export { default } from './pages/QrTracingPage';
/** The public page a scanned code opens. Routed at /trace/:token, outside the app shell. */
export const loadPublicTracePage = () => import('./pages/PublicTracePage');
