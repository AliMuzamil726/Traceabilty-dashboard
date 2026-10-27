import '@/design-system/map.css';
import L from 'leaflet';
import { useEffect } from 'react';
import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet';
import { EmptyState } from '@/design-system/components';
import { REGION_CENTRES, useTileLayers } from '@/module_2';
import type { Crop, TraceField } from '../api/types';

const OUTLINE = { color: '#00A651', weight: 3, fillColor: '#00A651', fillOpacity: 0.2 };
const ACTIVE = { color: '#00A651', weight: 3, fillColor: '#00A651', fillOpacity: 0.2 };

function Fit({ fields, focus }: { fields: TraceField[]; focus: string | null }) {
  const map = useMap();
  useEffect(() => {
    const chosen = focus ? fields.filter((f) => f.field_id === focus) : fields;
    const layer = L.geoJSON(chosen.filter((f) => f.geometry).map((f) => ({ type: 'Feature', properties: {}, geometry: f.geometry })) as never);
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 18 });
  }, [map, fields, focus]);
  return null;
}

/** Field outlines on satellite imagery, using Register's shared MapTiler Hybrid 2026 HD map settings. */
export function FieldTraceMap({ fields, crop, focus, onSelect }: { fields: TraceField[]; crop: Crop; focus: string | null; onSelect: (id: string) => void }) {
  const tiles = useTileLayers();
  const drawable = fields.filter((f) => f.geometry);
  if (!drawable.length) return <EmptyState compact title="No field outlines" description="These fields have no mapped boundary." />;
  const centre = REGION_CENTRES[crop === 'cotton' ? 'PK' : 'GB'] ?? { lat: 30.1575, lng: 71.5249, zoom: 18 };
  return (
    <div className="h-96 overflow-hidden rounded-card border border-line shadow-1">
      <MapContainer center={[centre.lat, centre.lng]} zoom={centre.zoom} minZoom={4} maxZoom={22} className="h-full w-full" scrollWheelZoom={false} attributionControl>
        <TileLayer
          url={tiles.satellite.url}
          attribution={tiles.satellite.attribution}
          maxZoom={22}
          tileSize={tiles.satellite.tileSize ?? 512}
          zoomOffset={tiles.satellite.zoomOffset ?? -1}
        />
        {tiles.labelsOn && (
          <TileLayer url={tiles.labels.url} attribution={tiles.labels.attribution} maxZoom={22} maxNativeZoom={19} />
        )}
        {drawable.map((f) => (
          <GeoJSON key={`${f.field_id}-${focus === f.field_id}`} data={f.geometry as never} style={focus === f.field_id ? ACTIVE : OUTLINE}
            eventHandlers={{ click: () => onSelect(f.field_id) }} />
        ))}
        <Fit fields={drawable} focus={focus} />
      </MapContainer>
    </div>
  );
}
