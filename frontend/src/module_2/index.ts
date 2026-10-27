/** Public entry of module 2. Other code imports this module only through this file. */
export { meta } from './module.meta';
export { default } from './pages/RegisterFarmerPage';
/** Shared map configuration (base layers, region centres), reused by Harvest Radar. */
export {
  BASE_LAYERS,
  GEOMETRY_ZOOM,
  LABELS,
  REGION_CENTRES,
  SATELLITE,
  STREET,
  type BaseLayerId,
  type TileLayerConfig,
} from './map/tileLayers';
export { useTileLayers, type BaseLayers } from './map/useTileLayers';
