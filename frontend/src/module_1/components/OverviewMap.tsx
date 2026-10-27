import '@/design-system/map.css';
import L, { type PathOptions } from 'leaflet';
import 'leaflet.markercluster';
import { Search, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { LayersControl, MapContainer, TileLayer, useMap } from 'react-leaflet';
import { formatNumber } from '@/core/utils/format';
import { cn } from '@/core/utils/cn';
import { EmptyState } from '@/design-system/components/EmptyState';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { Skeleton } from '@/design-system/components/Skeleton';
import { GEOMETRY_ZOOM, REGION_CENTRES, useTileLayers } from '@/module_2';
import type { CropFilter, MapCollection, MapFeature } from '../api/types';
import { BUCKET_HEX, BUCKET_ORDER, CROP_HEX, HEX } from '../lib/format';

export type MapLayer = 'crop' | 'readiness';

/** Which farmer the map is looking at, and which of their fields is open. */
interface Focus {
  farmerId: string | null;
  fieldId: string | null;
}

const NO_FOCUS: Focus = { farmerId: null, fieldId: null };

interface FarmerMatch {
  farmerId: string;
  sawieId: number;
  name: string;
  fields: MapFeature[];
}

/** Farmers on this map whose SAWIE ID or name matches what was typed. */
function matchFarmers(data: MapCollection | undefined, term: string): FarmerMatch[] {
  const text = term.trim().toLowerCase();
  if (!data || text.length === 0) return [];
  const byFarmer = new Map<string, FarmerMatch>();
  for (const feature of data.features) {
    const p = feature.properties;
    if (!String(p.sawie_id).startsWith(text) && !p.farmer_name.toLowerCase().includes(text)) continue;
    const found = byFarmer.get(p.farmer_id);
    if (found) found.fields.push(feature);
    else byFarmer.set(p.farmer_id, { farmerId: p.farmer_id, sawieId: p.sawie_id, name: p.farmer_name, fields: [feature] });
  }
  return [...byFarmer.values()].sort((a, b) => a.sawieId - b.sawieId).slice(0, 8);
}

export interface OverviewMapProps {
  crop: CropFilter;
  data: MapCollection | undefined;
  loading: boolean;
}

function colourFor(feature: MapFeature, layer: MapLayer): string {
  const p = feature.properties;
  return layer === 'crop' ? CROP_HEX[p.crop] : BUCKET_HEX[p.status];
}

function styleFor(feature: MapFeature, layer: MapLayer): PathOptions {
  const colour = colourFor(feature, layer);
  const overdue = feature.properties.overdue;
  return {
    color: overdue ? HEX.wheat600 : '#00A651',
    weight: 3,
    dashArray: overdue ? '6 4' : undefined,
    opacity: 1,
    fillColor: layer === 'crop' ? '#00A651' : colour,
    fillOpacity: 0.2,
  };
}

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c,
  );
}

function popupHtml(feature: MapFeature): string {
  const p = feature.properties;
  return [
    '<div style="min-width:186px">',
    `<div class="mono-id" style="font-weight:600">${escapeHtml(p.field_code)}</div>`,
    `<div style="margin-top:2px">${escapeHtml(p.farmer_name)}</div>`,
    `<div style="margin-top:2px;color:${HEX.muted}">SAWIE ID <span class="mono-id">${p.sawie_id}</span></div>`,
    `<div style="margin-top:6px">${formatNumber(p.area, 2)} ${escapeHtml(p.area_unit)}</div>`,
    `<div style="margin-top:2px"><strong>${escapeHtml(p.status_label)}</strong>${p.overdue ? ', overdue' : ''}</div>`,
    '</div>',
  ].join('');
}

function MapResizeHandler() {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      map.invalidateSize({ animate: false });
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [map]);
  return null;
}

/** Flies the map to a chosen farmer's fields, and right into one when it is picked. */
function FocusLayer({ data, focus }: { data: MapCollection | undefined; focus: Focus }) {
  const map = useMap();
  useEffect(() => {
    if (!data || !focus.farmerId) return;
    const mine = data.features.filter((f) => f.properties.farmer_id === focus.farmerId);
    if (mine.length === 0) return;
    const one = focus.fieldId ? mine.find((f) => f.properties.field_id === focus.fieldId) : undefined;
    if (one) {
      const [lng, lat] = one.properties.centroid;
      map.flyTo([lat, lng], 18, { duration: 0.6 });
      L.popup({ offset: [0, -6] }).setLatLng([lat, lng]).setContent(popupHtml(one)).openOn(map);
      return;
    }
    const bounds = L.latLngBounds(
      mine.map((f) => [f.properties.centroid[1], f.properties.centroid[0]] as [number, number]),
    );
    map.flyToBounds(bounds.pad(0.3), { maxZoom: 18, duration: 0.6 });
  }, [data, focus, map]);
  return null;
}

function FeaturesLayer({ data, layer, focused }: { data: MapCollection | undefined; layer: MapLayer; focused: boolean }) {
  const map = useMap();
  const group = useRef<L.LayerGroup>(L.layerGroup());
  const [zoom, setZoom] = useState(map.getZoom());

  useEffect(() => {
    group.current.addTo(map);
    const onZoom = () => setZoom(map.getZoom());
    map.on('zoomend', onZoom);
    return () => {
      map.off('zoomend', onZoom);
    };
  }, [map]);

  // Outlines when close enough to read them, clustered points further out.
  useEffect(() => {
    const layers = group.current;
    layers.clearLayers();
    if (!data) return;
    if (zoom < GEOMETRY_ZOOM) {
      const cluster = L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 60,
        iconCreateFunction: (c) => {
          const count = c.getChildCount();
          return L.divIcon({
            html: `<span class="sawie-cluster${count > 99 ? ' sawie-cluster--large' : ''}">${count}</span>`,
            className: '',
            iconSize: count > 99 ? [44, 44] : [36, 36],
          });
        },
      });
      for (const feature of data.features) {
        const [lng, lat] = feature.properties.centroid;
        const marker = L.circleMarker([lat, lng], {
          ...styleFor(feature, layer),
          radius: 7,
          fillOpacity: 0.9,
        });
        marker.bindPopup(popupHtml(feature));
        cluster.addLayer(marker);
      }
      layers.addLayer(cluster);
      return;
    }
    for (const feature of data.features) {
      if (!feature.geometry) continue;
      const outline = L.geoJSON(feature.geometry, { style: styleFor(feature, layer) });
      outline.bindPopup(popupHtml(feature));
      layers.addLayer(outline);
    }
  }, [data, layer, zoom]);

  // Fit to the fields whenever the set changes.
  const fitted = useRef('');
  useEffect(() => {
    if (!data?.features.length || focused) return;
    const signature = data.features.map((f) => f.id).join(',');
    if (signature === fitted.current) return;
    fitted.current = signature;
    const bounds = L.latLngBounds(
      data.features.map((f) => [f.properties.centroid[1], f.properties.centroid[0]] as [number, number]),
    );
    map.fitBounds(bounds.pad(0.5), { maxZoom: 15 });
  }, [data, map, focused]);

  return null;
}

function MapLegend({ layer }: { layer: MapLayer }) {
  const items =
    layer === 'crop'
      ? [
          { key: 'cotton', label: 'Cotton', colour: '#00A651' },
          { key: 'hemp', label: 'Hemp', colour: CROP_HEX.hemp },
        ]
      : BUCKET_ORDER.map((bucket) => ({
          key: bucket,
          label: bucket.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()),
          colour: BUCKET_HEX[bucket],
        }));
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Map legend">
      {items.map((item) => (
        <li key={item.key} className="flex items-center gap-1.5">
          <span
            className="h-3 w-3 rounded-sm border border-line"
            style={{ backgroundColor: item.colour }}
            aria-hidden
          />
          {item.label}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span className="h-3 w-3 rounded-sm border-2 border-dashed border-wheat-600" aria-hidden />
        Overdue
      </li>
    </ul>
  );
}

/** Find a farmer on the map by SAWIE ID or name, then open one of their fields. */
function FarmerFinder({
  data,
  focus,
  onFocus,
}: {
  data: MapCollection | undefined;
  focus: Focus;
  onFocus: (focus: Focus) => void;
}) {
  const [term, setTerm] = useState('');
  const matches = useMemo(() => matchFarmers(data, term), [data, term]);
  const chosen = matches.find((m) => m.farmerId === focus.farmerId) ?? null;
  const searching = term.trim().length > 0;

  return (
    <div className="flex flex-col gap-2">
      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
        <input
          type="search"
          value={term}
          aria-label="Find a farmer on the map by SAWIE ID or name"
          placeholder="Find a farmer: SAWIE ID or name"
          onChange={(e) => {
            setTerm(e.target.value);
            onFocus(NO_FOCUS);
          }}
          className="h-9 w-full rounded-control border border-line bg-canvas pl-9 pr-8 text-base text-ink placeholder:text-muted focus:border-forest-500 focus:bg-surface focus:outline-none"
        />
        {searching && (
          <button
            type="button"
            aria-label="Clear"
            onClick={() => {
              setTerm('');
              onFocus(NO_FOCUS);
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-control p-1 text-muted hover:text-ink"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        )}
      </div>

      {searching && matches.length === 0 && (
        <p className="text-sm text-muted">
          No farmer on this map matches that. Check the crop and the season above.
        </p>
      )}

      {searching && matches.length > 0 && !chosen && (
        <ul className="flex flex-wrap gap-2">
          {matches.map((m) => (
            <li key={m.farmerId}>
              <button
                type="button"
                onClick={() => onFocus({ farmerId: m.farmerId, fieldId: null })}
                className="rounded-control border border-line bg-surface px-3 py-1.5 text-sm text-ink hover:bg-forest-50"
              >
                <span className="mono-id font-medium">{m.sawieId}</span> {m.name}
                <span className="text-muted"> · {m.fields.length} field{m.fields.length === 1 ? '' : 's'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {chosen && (
        <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-ink">
              <span className="mono-id font-medium">{chosen.sawieId}</span> {chosen.name}
              <span className="text-muted"> · pick a field to zoom in</span>
            </p>
            <button
              type="button"
              onClick={() => onFocus({ farmerId: chosen.farmerId, fieldId: null })}
              className="text-sm text-forest-800 hover:underline"
            >
              All fields
            </button>
          </div>
          <ul className="flex flex-wrap gap-2">
            {chosen.fields.map((field) => {
              const p = field.properties;
              const active = focus.fieldId === p.field_id;
              return (
                <li key={p.field_id}>
                  <button
                    type="button"
                    onClick={() => onFocus({ farmerId: chosen.farmerId, fieldId: p.field_id })}
                    className={cn(
                      'rounded-control border px-3 py-1.5 text-sm',
                      active ? 'border-forest-600 bg-forest-50 text-forest-800' : 'border-line bg-surface text-ink hover:bg-forest-50',
                    )}
                  >
                    <span className="mono-id">{p.field_code}</span>
                    <span className="text-muted"> · {formatNumber(p.area, 2)} {p.area_unit}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Every field in the filter on one satellite map, coloured by crop programme or by
 * readiness. Built from the map pieces Module 2 exports, with MapTiler Hybrid 2026 HD
 * tiles up to zoom 22 and default farm-level view at [30.1575, 71.5249].
 */
export default function OverviewMap({ crop, data, loading }: OverviewMapProps) {
  const tiles = useTileLayers();
  const [layer, setLayer] = useState<MapLayer>('readiness');
  const [focus, setFocus] = useState<Focus>(NO_FOCUS);
  const centre = REGION_CENTRES[crop === 'hemp' ? 'GB' : 'PK'] ?? { lat: 30.1575, lng: 71.5249, zoom: 18 };
  const hasFeatures = Boolean(data && data.features.length > 0);

  if (loading && !data) return <Skeleton className="h-[480px] w-full lg:h-[540px]" shape="block" />;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <MapLegend layer={layer} />
        <SegmentedControl
          aria-label="Colour the fields by"
          value={layer}
          onChange={setLayer}
          size="sm"
          options={[
            { value: 'readiness', label: 'Readiness' },
            { value: 'crop', label: 'Crop' },
          ]}
        />
      </div>

      {hasFeatures && <FarmerFinder data={data} focus={focus} onFocus={setFocus} />}

      <div className="relative h-[480px] w-full overflow-hidden rounded-card border border-line shadow-1 lg:h-[540px]">
        <MapContainer
          center={[centre.lat, centre.lng]}
          zoom={Math.min(centre.zoom ?? 18, 14)}
          minZoom={4}
          maxZoom={22}
          className="h-full w-full"
          scrollWheelZoom
          attributionControl
        >
          <MapResizeHandler />
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name={tiles.satellite.label}>
              <TileLayer
                url={tiles.satellite.url}
                attribution={tiles.satellite.attribution}
                maxZoom={22}
                tileSize={tiles.satellite.tileSize ?? 512}
                zoomOffset={tiles.satellite.zoomOffset ?? -1}
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name={tiles.street.label}>
              <TileLayer
                url={tiles.street.url}
                attribution={tiles.street.attribution}
                maxZoom={22}
                tileSize={tiles.street.tileSize ?? 512}
                zoomOffset={tiles.street.zoomOffset ?? -1}
              />
            </LayersControl.BaseLayer>
            <LayersControl.Overlay checked={tiles.labelsOn} name={tiles.labels.label}>
              <TileLayer
                url={tiles.labels.url}
                attribution={tiles.labels.attribution}
                maxZoom={22}
                maxNativeZoom={19}
              />
            </LayersControl.Overlay>
          </LayersControl>
          <FeaturesLayer data={data} layer={layer} focused={Boolean(focus.farmerId)} />
          <FocusLayer data={data} focus={focus} />
        </MapContainer>
      </div>

      {!hasFeatures && (
        <EmptyState
          compact
          title="No fields to show"
          description="Map a field in Register Farmer and it appears here. Showing HD farm view centered at Multan."
        />
      )}

      {data?.truncated && (
        <p className="text-xs text-muted">
          Showing the first {formatNumber(data.returned)} of {formatNumber(data.total)} fields.
          Narrow the crop or the season to see the rest.
        </p>
      )}
    </div>
  );
}
