import '@/design-system/map.css';
import L, { type PathOptions } from 'leaflet';
import 'leaflet.markercluster';
import { useEffect, useRef, useState } from 'react';
import { LayersControl, MapContainer, TileLayer, useMap } from 'react-leaflet';
import { EmptyState, Skeleton } from '@/design-system/components';
import { GEOMETRY_ZOOM, REGION_CENTRES, useTileLayers } from '@/module_2';
import type { Crop, MapCollection, MapFeature } from '../api/types';
import { BUCKET_HEX, BUCKET_LABEL, BUCKET_ORDER, HEX, PICKUP_LABEL } from '../lib/status';

export interface RadarMapProps {
  crop: Crop;
  data: MapCollection | undefined;
  loading: boolean;
  /** "View on map" from the table: zoom to this field and open its popup. */
  focusFieldId: string | null;
  onRequest: (fieldId: string) => void;
}

function styleFor(feature: MapFeature): PathOptions {
  const colour = BUCKET_HEX[feature.properties.status];
  const overdue = feature.properties.overdue;
  return {
    color: overdue ? HEX.wheat600 : '#00A651',
    weight: 3,
    dashArray: overdue ? '6 4' : undefined,
    opacity: 1,
    fillColor: colour === HEX.line ? '#00A651' : colour,
    fillOpacity: 0.2,
  };
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c);
}

function popupHtml(f: MapFeature): string {
  const p = f.properties;
  return [
    '<div style="min-width:190px">',
    `<div class="mono-id" style="font-weight:600">${escapeHtml(p.field_code)}</div>`,
    `<div style="margin-top:2px">${escapeHtml(p.farmer_name)}</div>`,
    `<div style="margin-top:2px;color:${HEX.muted}">SAWIE ID <span class="mono-id">${p.sawie_id}</span></div>`,
    `<div style="margin-top:6px"><strong>${escapeHtml(p.status_label)}</strong>${p.overdue ? ', overdue' : ''}</div>`,
    `<div style="color:${HEX.muted}">${escapeHtml(p.next_milestone)}</div>`,
    `<div style="color:${HEX.muted}">Pickup: ${escapeHtml(PICKUP_LABEL[p.pickup_state])}</div>`,
    p.can_request
      ? `<button type="button" data-request="${escapeHtml(p.field_id)}" class="sawie-popup-button">Request pickup</button>`
      : '',
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

function FeaturesLayer({ data, focusFieldId, onRequest }: Omit<RadarMapProps, 'crop' | 'loading'>) {
  const map = useMap();
  const group = useRef<L.LayerGroup>(L.layerGroup());
  const layers = useRef(new Map<string, L.Layer>());
  const [zoom, setZoom] = useState(map.getZoom());

  useEffect(() => {
    group.current.addTo(map);
    const onZoom = () => setZoom(map.getZoom());
    // The popup's Request pickup button is plain HTML; catch its clicks here.
    const onClick = (e: MouseEvent) => {
      const id = (e.target as HTMLElement).closest<HTMLElement>('[data-request]')?.dataset.request;
      if (id) onRequest(id);
    };
    const container = map.getContainer();
    map.on('zoomend', onZoom);
    container.addEventListener('click', onClick);
    return () => {
      map.off('zoomend', onZoom);
      container.removeEventListener('click', onClick);
    };
  }, [map, onRequest]);

  // Draw: outlines when close enough to read them, clustered points further out.
  useEffect(() => {
    const g = group.current;
    g.clearLayers();
    layers.current.clear();
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
      for (const f of data.features) {
        const [lng, lat] = f.properties.centroid;
        const marker = L.circleMarker([lat, lng], { ...styleFor(f), radius: 7, fillOpacity: 0.9 });
        marker.bindPopup(popupHtml(f));
        layers.current.set(f.properties.field_id, marker);
        cluster.addLayer(marker);
      }
      g.addLayer(cluster);
      return;
    }
    for (const f of data.features) {
      if (!f.geometry) continue;
      const layer = L.geoJSON(f.geometry, { style: styleFor(f) });
      layer.bindPopup(popupHtml(f));
      layers.current.set(f.properties.field_id, layer);
      g.addLayer(layer);
    }
  }, [data, zoom]);

  // Fit to the filtered fields whenever the set changes.
  const fitted = useRef<string>('');
  useEffect(() => {
    if (!data?.features.length || focusFieldId) return;
    const signature = data.features.map((f) => f.id).join(',');
    if (signature === fitted.current) return;
    fitted.current = signature;
    const bounds = L.latLngBounds(data.features.map((f) => [f.properties.centroid[1], f.properties.centroid[0]] as [number, number]));
    map.fitBounds(bounds.pad(0.2), { maxZoom: 18 });
  }, [data, map, focusFieldId]);

  // Zoom to one field on request, then open its popup.
  useEffect(() => {
    if (!focusFieldId || !data) return;
    const f = data.features.find((x) => x.properties.field_id === focusFieldId);
    if (!f) return;
    const [lng, lat] = f.properties.centroid;
    map.setView([lat, lng], 18);
    const t = window.setTimeout(() => {
      const layer = layers.current.get(focusFieldId) as (L.Layer & { openPopup?: () => void }) | undefined;
      layer?.openPopup?.();
    }, 400);
    return () => window.clearTimeout(t);
  }, [focusFieldId, data, map]);

  return null;
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Map legend">
      {BUCKET_ORDER.map((b) => (
        <li key={b} className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm border border-line" style={{ backgroundColor: BUCKET_HEX[b] }} aria-hidden />
          {BUCKET_LABEL[b]}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span className="h-3 w-3 rounded-sm border-2 border-dashed border-wheat-600" aria-hidden />
        Overdue
      </li>
    </ul>
  );
}

export function RadarMap({ crop, data, loading, focusFieldId, onRequest }: RadarMapProps) {
  const layers = useTileLayers();
  const centre = REGION_CENTRES[crop === 'cotton' ? 'PK' : 'GB'] ?? { lat: 30.1575, lng: 71.5249, zoom: 18 };
  if (loading && !data) return <Skeleton className="h-[580px] w-full" shape="block" />;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Legend />
        {data?.truncated && <p className="text-xs text-muted">Showing the first {data.features.length} of {data.total} fields. Narrow the filters to see the rest.</p>}
      </div>
      {data && data.features.length === 0 ? (
        <EmptyState title="No fields to show" description="Change or clear the filters to see fields on the map." />
      ) : (
        <div className="h-[580px] w-full overflow-hidden rounded-card border border-line shadow-1">
          <MapContainer center={[centre.lat, centre.lng]} zoom={centre.zoom ?? 18} minZoom={4} maxZoom={22} className="h-full w-full" scrollWheelZoom attributionControl>
            <MapResizeHandler />
            <LayersControl position="topright">
              <LayersControl.BaseLayer checked name={layers.satellite.label}>
                <TileLayer
                  url={layers.satellite.url}
                  attribution={layers.satellite.attribution}
                  maxZoom={22}
                  tileSize={layers.satellite.tileSize ?? 512}
                  zoomOffset={layers.satellite.zoomOffset ?? -1}
                />
              </LayersControl.BaseLayer>
              <LayersControl.BaseLayer name={layers.street.label}>
                <TileLayer
                  url={layers.street.url}
                  attribution={layers.street.attribution}
                  maxZoom={22}
                  tileSize={layers.street.tileSize ?? 512}
                  zoomOffset={layers.street.zoomOffset ?? -1}
                />
              </LayersControl.BaseLayer>
              <LayersControl.Overlay checked={layers.labelsOn} name={layers.labels.label}>
                <TileLayer url={layers.labels.url} attribution={layers.labels.attribution} maxZoom={22} maxNativeZoom={19} />
              </LayersControl.Overlay>
            </LayersControl>
            <FeaturesLayer data={data} focusFieldId={focusFieldId} onRequest={onRequest} />
          </MapContainer>
        </div>
      )}
    </div>
  );
}
