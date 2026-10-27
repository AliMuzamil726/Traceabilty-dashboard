import { useState } from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { toast } from '@/design-system/components/toastStore';
import { SATELLITE } from '@/module_2';
import { settingsApi } from '../api/client';
import { useAppConfig } from '../hooks/useAppConfig';
import { GroupPage } from './GroupPage';

/** Tile provider, labels and default centres, with a live preview. */
export default function MapPage() {
  const config = useAppConfig();
  const [testing, setTesting] = useState(false);
  const rawTiles = config.data?.map.tiles;
  const isDefaultEsri = !rawTiles || rawTiles.key === 'esri_imagery' || rawTiles.url.includes('arcgisonline.com');
  const tiles = isDefaultEsri
    ? {
        key: SATELLITE.id,
        label: SATELLITE.label,
        url: SATELLITE.url,
        attribution: SATELLITE.attribution,
        max_zoom: SATELLITE.maxZoom,
        tile_size: SATELLITE.tileSize,
        zoom_offset: SATELLITE.zoomOffset,
        fallback_reason: rawTiles?.fallback_reason,
      }
    : rawTiles;

  const test = async () => {
    if (!rawTiles) return;
    setTesting(true);
    try {
      const result = await settingsApi.testTiles(rawTiles.key);
      if (result.ok) toast.success('Tiles reached', result.detail);
      else toast.error('Tiles could not be reached', result.detail);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <GroupPage
        group="map"
        title="Map"
        description="Every map in the product reads these: the register, Harvest Radar, the dashboard and the public page."
        notice={
          <p className="rounded-control bg-forest-50 px-3 py-2 text-sm text-ink">
            A tile provider's licence requires its credit line to stay visible. The attribution
            below is drawn on every map and cannot be removed.
          </p>
        }
      />

      <Card padding="md">
        <SectionHeader
          title="Preview"
          description="What officers will see, using the settings in force right now."
          actions={
            <Button variant="secondary" size="sm" loading={testing} onClick={() => void test()}>
              Test tiles
            </Button>
          }
        />
        <div className="mt-3 h-80 overflow-hidden rounded-card border border-line">
          {tiles && (
            <MapContainer
              key={`${tiles.key}-${tiles.url}`}
              center={[30.1575, 71.5249]}
              zoom={18}
              minZoom={4}
              maxZoom={22}
              className="h-full w-full"
              attributionControl
            >
              <TileLayer
                url={tiles.url}
                attribution={tiles.attribution}
                maxZoom={22}
                tileSize={tiles.tile_size ?? 512}
                zoomOffset={tiles.zoom_offset ?? -1}
              />
              {config.data?.map.labels_overlay && config.data.map.labels_overlay_url && (
                <TileLayer
                  url={config.data.map.labels_overlay_url}
                  attribution={tiles.attribution}
                  maxZoom={22}
                  maxNativeZoom={19}
                />
              )}
            </MapContainer>
          )}
        </div>
        {tiles?.fallback_reason && (
          <p className="mt-2 rounded-control bg-wheat-50 px-3 py-2 text-sm text-ink">
            {tiles.fallback_reason}
          </p>
        )}
      </Card>
    </div>
  );
}
