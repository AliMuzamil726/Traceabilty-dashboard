import '@/design-system/map.css';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import 'leaflet.markercluster';
import { intersect } from '@turf/turf';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import { formatDecimal } from '@/core/utils/format';
import { registerApi, registerKeys } from '../api/client';
import type { Field, MapFeature, OverlapConflict, PolygonGeometry } from '../api/types';
import {
  ACCURACY_STYLE,
  DRAFT_STYLE,
  OVERLAP_STYLE,
  OWN_FIELD_STYLE,
  SELECTED_STYLE,
  styleForCrop,
} from '../map/style';
import {
  DEFAULT_ZOOM,
  GEOMETRY_ZOOM,
  REGION_CENTRES,
} from '../map/tileLayers';
import { useTileLayers } from '../map/useTileLayers';
import { useMapStore } from '../store/mapStore';
import type { Position } from '../hooks/useGeolocation';
import { useQuery } from '@tanstack/react-query';

const MAP_MOVE_DEBOUNCE_MS = 250;
const MAP_FEATURE_LIMIT = 2000;

/** Imperative handle, so the design-system toolbar can drive the map. */
export interface FieldMapHandle {
  startDraw: () => void;
  cancelDraw: () => void;
  toggleEdit: () => void;
  startPin: () => void;
  deleteDraft: () => void;
  undoVertex: () => void;
  flyTo: (lat: number, lng: number, zoom?: number) => void;
  fitField: (field: Field) => void;
  fitAllFields: () => void;
  invalidate: () => void;
}

export interface DraftState {
  geometry: PolygonGeometry | null;
  pin: { lat: number; lng: number } | null;
}

export interface FieldMapProps {
  farmerId: string;
  farmerName?: string;
  farmerSawieId?: number;
  country: string;
  /** This farmer's saved fields, drawn thicker than the context layer. */
  farmerFields: Field[];
  /** Field being reshaped, excluded from the context layer so it is not drawn twice. */
  editingFieldId?: string | null;
  draft: DraftState;
  onDraftChange: (draft: DraftState) => void;
  conflicts: OverlapConflict[];
  position: Position | null;
  selectedFieldId: string | null;
  onSelectField: (fieldId: string | null) => void;
  handleRef: React.MutableRefObject<FieldMapHandle | null>;
  onToolChange: (state: { drawing: boolean; editing: boolean }) => void;
}

interface GeomanDrawShape {
  _removeLastVertex?: () => void;
}

function ringSignature(geometry: PolygonGeometry | null): string {
  return geometry ? JSON.stringify(geometry.coordinates) : '';
}

function toPolygonGeometry(layer: L.Polygon): PolygonGeometry | null {
  const geojson = layer.toGeoJSON() as GeoJSON.Feature;
  if (!geojson.geometry || geojson.geometry.type !== 'Polygon') return null;
  return geojson.geometry as PolygonGeometry;
}

/* -------------------------------------------------------------------------- */
/* Responsive resize observer so the map never shows grey gaps on laptops      */
/* -------------------------------------------------------------------------- */

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

/* -------------------------------------------------------------------------- */
/* Follow the officer's position when the farmer has no fields yet             */
/* -------------------------------------------------------------------------- */

/**
 * Leaflet reads ``MapContainer``'s centre once, when it mounts, so a GPS fix that
 * arrives afterwards would leave a new farmer's map on the region centre. Follow the
 * first fix instead, unless this farmer already has a field to fit.
 */
function CentreOnPosition({ position, enabled }: { position: Position | null; enabled: boolean }) {
  const map = useMap();
  const followed = useRef(false);
  useEffect(() => {
    if (!enabled || followed.current || !position) return;
    followed.current = true;
    map.flyTo([position.lat, position.lng], Math.max(map.getZoom(), GEOMETRY_ZOOM), {
      duration: 0.8,
    });
  }, [enabled, position, map]);
  return null;
}

/* -------------------------------------------------------------------------- */
/* Context layer: every field in the database + all fields of current farmer   */
/* -------------------------------------------------------------------------- */

function useViewport(map: L.Map) {
  const [viewport, setViewport] = useState(() => ({
    bbox: undefined as string | undefined,
    zoom: Math.min(22, Math.round(map.getZoom())),
  }));

  useEffect(() => {
    let timer: number | undefined;
    const update = () => {
      window.clearTimeout(timer);
      // The officer pans continuously; only the view they settle on is worth a request.
      timer = window.setTimeout(() => {
        const bounds = map.getBounds();
        setViewport({
          bbox: [
            bounds.getWest(),
            bounds.getSouth(),
            bounds.getEast(),
            bounds.getNorth(),
          ].join(','),
          zoom: Math.min(22, Math.round(map.getZoom())),
        });
      }, MAP_MOVE_DEBOUNCE_MS);
    };
    update();
    map.on('moveend zoomend', update);
    return () => {
      window.clearTimeout(timer);
      map.off('moveend zoomend', update);
    };
  }, [map]);

  return viewport;
}

function AllFieldsLayer({
  farmerId,
  farmerName,
  farmerSawieId,
  country,
  farmerFields,
  editingFieldId,
  selectedFieldId,
  onSelectField,
  onFeatures,
}: {
  farmerId: string;
  farmerName?: string;
  farmerSawieId?: number;
  country: string;
  farmerFields: Field[];
  editingFieldId?: string | null;
  selectedFieldId: string | null;
  onSelectField: (id: string | null) => void;
  onFeatures: (features: MapFeature[]) => void;
}) {
  const map = useMap();
  const { bbox, zoom } = useViewport(map);
  const showAllFields = useMapStore((s) => s.showAllFields);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const ownLayerRef = useRef<L.LayerGroup | null>(null);

  // Viewport fields + global fallback so all mapped fields across the officer's area load
  const { data } = useQuery({
    queryKey: registerKeys.map(bbox, Math.max(zoom, GEOMETRY_ZOOM)),
    queryFn: ({ signal }) =>
      registerApi.mapFields({ bbox, zoom: Math.max(zoom, GEOMETRY_ZOOM), limit: MAP_FEATURE_LIMIT }, signal),
    staleTime: 15_000,
  });

  // Also fetch the full set of mapped fields (without bbox restriction) so any field mapped
  // by the officer is always visible on the map regardless of initial pan position.
  const { data: globalData } = useQuery({
    queryKey: registerKeys.map(undefined, GEOMETRY_ZOOM),
    queryFn: ({ signal }) =>
      registerApi.mapFields({ zoom: GEOMETRY_ZOOM, limit: MAP_FEATURE_LIMIT }, signal),
    staleTime: 15_000,
  });

  const combinedItems = useMemo(() => {
    const byId = new Map<string, MapFeature>();
    for (const item of globalData?.items ?? []) byId.set(item.id, item);
    for (const item of data?.items ?? []) byId.set(item.id, item);
    return [...byId.values()];
  }, [data, globalData]);

  useEffect(() => {
    onFeatures(combinedItems);
  }, [combinedItems, onFeatures]);

  useEffect(() => {
    const group = L.layerGroup().addTo(map);
    const ownGroup = L.layerGroup().addTo(map);
    layerRef.current = group;
    ownLayerRef.current = ownGroup;
    return () => {
      group.remove();
      ownGroup.remove();
      layerRef.current = null;
      ownLayerRef.current = null;
    };
  }, [map]);

  // 1. Always render all saved fields of the current farmer as polygons with permanent labels
  useEffect(() => {
    const ownGroup = ownLayerRef.current;
    if (!ownGroup) return;
    ownGroup.clearLayers();

    for (const field of farmerFields) {
      if (!field.geometry || field.id === editingFieldId) continue;
      const selected = field.id === selectedFieldId;
      const style = selected ? SELECTED_STYLE : OWN_FIELD_STYLE;
      const layer = L.geoJSON(field.geometry, { style, interactive: true });
      layer.bindPopup(
        popupHtml({
          id: field.id,
          field_id: field.field_id,
          farmer_id: field.farmer_id,
          farmer_name: farmerName ?? 'Current farmer',
          sawie_id: farmerSawieId ?? 0,
          crop: country === 'GB' ? 'hemp' : 'cotton',
          area_acre: field.area_acre,
          area_ha: field.area_ha,
          pin_lat: field.pin_lat,
          pin_lng: field.pin_lng,
          geometry: field.geometry,
        }),
      );
      layer.bindTooltip(
        `${field.field_id} (${country === 'GB' ? `${formatDecimal(field.area_ha, 2)} ha` : `${formatDecimal(field.area_acre, 2)} ac`})`,
        {
          permanent: zoom >= 15,
          direction: 'center',
        },
      );
      layer.on('click', () => onSelectField(field.id));
      ownGroup.addLayer(layer);
    }
  }, [farmerFields, farmerName, farmerSawieId, country, editingFieldId, selectedFieldId, onSelectField, zoom]);

  // 2. Render all other mapped fields across the officer's database
  useEffect(() => {
    const group = layerRef.current;
    if (!group) return;
    group.clearLayers();
    if (!showAllFields || combinedItems.length === 0) return;

    const ownIds = new Set(farmerFields.map((f) => f.id));
    const otherFeatures = combinedItems.filter(
      (f) => f.farmer_id !== farmerId && !ownIds.has(f.id) && f.id !== editingFieldId,
    );

    if (zoom < GEOMETRY_ZOOM) {
      const cluster = L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 60,
        iconCreateFunction: (group_) => {
          const count = group_.getChildCount();
          return L.divIcon({
            html: `<span class="sawie-cluster${count > 99 ? ' sawie-cluster--large' : ''}">${count}</span>`,
            className: '',
            iconSize: count > 99 ? [44, 44] : [36, 36],
          });
        },
      });
      for (const feature of otherFeatures) {
        const marker = L.marker([feature.pin_lat, feature.pin_lng], {
          icon: L.divIcon({ html: '<span class="sawie-position-dot"></span>', className: '' }),
          title: `${feature.field_id} ${feature.farmer_name}`,
        });
        marker.bindPopup(popupHtml(feature));
        cluster.addLayer(marker);
      }
      group.addLayer(cluster);
      return;
    }

    for (const feature of otherFeatures) {
      if (!feature.geometry) continue;
      const style = styleForCrop(feature.crop);
      const layer = L.geoJSON(feature.geometry, { style, interactive: true });
      layer.bindPopup(popupHtml(feature));
      layer.bindTooltip(`${feature.field_id} · ${feature.farmer_name}`, {
        direction: 'top',
      });
      layer.on('click', () => onSelectField(null));
      group.addLayer(layer);
    }
  }, [combinedItems, showAllFields, farmerId, farmerFields, editingFieldId, onSelectField, zoom]);

  return null;
}

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (ch) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch] ?? ch,
  );
}

/** Popup for any field on the map: which field, whose, and how big. */
function popupHtml(feature: MapFeature): string {
  const area =
    feature.crop === 'hemp'
      ? `${formatDecimal(feature.area_ha, 2)} ha`
      : `${formatDecimal(feature.area_acre, 2)} acres`;
  return [
    '<div style="min-width:170px">',
    `<div class="mono-id" style="font-weight:600">${escapeHtml(feature.field_id)}</div>`,
    `<div style="margin-top:2px">${escapeHtml(feature.farmer_name)}</div>`,
    feature.sawie_id
      ? `<div style="margin-top:2px;color:#5B675F">SAWIE ID <span class="mono-id">${feature.sawie_id}</span></div>`
      : '',
    `<div style="margin-top:4px" class="tabular">${area}</div>`,
    '</div>',
  ].join('');
}

/* -------------------------------------------------------------------------- */
/* Officer position                                                            */
/* -------------------------------------------------------------------------- */

function PositionLayer({ position }: { position: Position | null }) {
  const map = useMap();
  useEffect(() => {
    if (!position) return;
    const marker = L.marker([position.lat, position.lng], {
      icon: L.divIcon({ html: '<span class="sawie-position-dot"></span>', className: '' }),
      interactive: false,
      keyboard: false,
    }).addTo(map);
    const circle = L.circle([position.lat, position.lng], {
      ...ACCURACY_STYLE,
      radius: Math.max(position.accuracy, 5),
      interactive: false,
    }).addTo(map);
    return () => {
      marker.remove();
      circle.remove();
    };
  }, [map, position]);
  return null;
}

/* -------------------------------------------------------------------------- */
/* The draft boundary: drawing, editing, pinning, overlap highlight            */
/* -------------------------------------------------------------------------- */

function DraftLayer({
  draft,
  onDraftChange,
  conflicts,
  features,
  farmerFields,
  handleRef,
  onToolChange,
}: {
  draft: DraftState;
  onDraftChange: (draft: DraftState) => void;
  conflicts: OverlapConflict[];
  features: MapFeature[];
  farmerFields: Field[];
  handleRef: React.MutableRefObject<FieldMapHandle | null>;
  onToolChange: (state: { drawing: boolean; editing: boolean }) => void;
}) {
  const map = useMap();
  const setTool = useMapStore((s) => s.setTool);
  const layerRef = useRef<L.Polygon | null>(null);
  const pinRef = useRef<L.CircleMarker | null>(null);
  const overlapRef = useRef<L.LayerGroup | null>(null);
  const emittedRef = useRef<string>('');
  const drawingRef = useRef(false);
  const editingRef = useRef(false);
  const pinningRef = useRef(false);

  const emit = useCallback(
    (geometry: PolygonGeometry | null, pin: { lat: number; lng: number } | null) => {
      emittedRef.current = ringSignature(geometry);
      onDraftChange({ geometry, pin });
    },
    [onDraftChange],
  );

  const readLayer = useCallback(() => {
    const layer = layerRef.current;
    if (!layer) return;
    const geometry = toPolygonGeometry(layer);
    emit(geometry, draft.pin);
  }, [emit, draft.pin]);

  const attach = useCallback(
    (layer: L.Polygon) => {
      layer.setStyle(DRAFT_STYLE);
      layerRef.current = layer;
      // Geoman fires these while the officer drags a vertex, adds one or removes one.
      layer.on('pm:edit pm:update pm:markerdragend pm:vertexadded pm:vertexremoved', readLayer);
    },
    [readLayer],
  );

  const clearLayer = useCallback(() => {
    const layer = layerRef.current;
    if (layer) {
      layer.off();
      if (layer.pm?.enabled()) layer.pm.disable();
      layer.remove();
    }
    layerRef.current = null;
    editingRef.current = false;
  }, []);

  /* Geoman global configuration. Self-intersection is refused while drawing, which
     stops most invalid shapes before the server has to reject them. */
  useEffect(() => {
    map.pm.setGlobalOptions({
      allowSelfIntersection: false,
      snappable: true,
      snapDistance: 15,
      hideMiddleMarkers: false,
      templineStyle: DRAFT_STYLE,
      hintlineStyle: { ...DRAFT_STYLE, dashArray: '5 5' },
      pathOptions: DRAFT_STYLE,
    });
  }, [map]);

  /* A finished drawing becomes the draft. Geoman adds its own layer to the map, so it
     is adopted rather than copied, which keeps its edit handles working. */
  useEffect(() => {
    const onCreate = (event: { layer: L.Layer; shape: string }) => {
      drawingRef.current = false;
      setTool('idle');
      onToolChange({ drawing: false, editing: false });
      if (!(event.layer instanceof L.Polygon)) {
        event.layer.remove();
        return;
      }
      clearLayer();
      attach(event.layer);
      emit(toPolygonGeometry(event.layer), null);
    };
    map.on('pm:create', onCreate);
    return () => {
      map.off('pm:create', onCreate);
    };
  }, [map, attach, clearLayer, emit, setTool, onToolChange]);

  /* Keep the layer in step with the draft held by the page. The signature guard stops
     the layer being rebuilt from its own emitted geometry, which would throw away the
     vertex handles mid-edit. */
  useEffect(() => {
    const signature = ringSignature(draft.geometry);
    if (signature === emittedRef.current && layerRef.current) return;
    if (!draft.geometry) {
      clearLayer();
      emittedRef.current = '';
      return;
    }
    clearLayer();
    const layer = L.geoJSON(draft.geometry, { style: DRAFT_STYLE });
    const first = layer.getLayers()[0];
    if (first instanceof L.Polygon) {
      first.addTo(map);
      attach(first);
      emittedRef.current = signature;
    }
  }, [draft.geometry, map, attach, clearLayer]);

  /* The pin. Placed by clicking the map while the pin tool is armed. */
  useEffect(() => {
    pinRef.current?.remove();
    pinRef.current = null;
    if (!draft.pin) return;
    pinRef.current = L.circleMarker([draft.pin.lat, draft.pin.lng], {
      radius: 7,
      color: '#FFFFFF',
      weight: 2,
      fillColor: '#C79A2E',
      fillOpacity: 1,
    })
      .addTo(map)
      .bindTooltip('Field pin');
  }, [map, draft.pin]);

  useEffect(() => {
    const onClick = (event: L.LeafletMouseEvent) => {
      if (!pinningRef.current) return;
      pinningRef.current = false;
      setTool('idle');
      map.getContainer().classList.remove('geoman-draw-cursor');
      emit(draft.geometry, { lat: event.latlng.lat, lng: event.latlng.lng });
    };
    map.on('click', onClick);
    return () => {
      map.off('click', onClick);
    };
  }, [map, emit, draft.geometry, setTool]);

  /* The overlapping area, in the error red. The server says which fields conflict; the
     intersection itself is computed here with turf so the officer can see exactly which
     sliver to move rather than being told a number. */
  const conflictGeometries = useMemo(() => {
    const byId = new Map<string, PolygonGeometry>();
    for (const feature of features) {
      if (feature.geometry) byId.set(feature.id, feature.geometry);
    }
    for (const field of farmerFields) byId.set(field.id, field.geometry);
    return conflicts
      .map((conflict) => byId.get(conflict.field_id))
      .filter((geometry): geometry is PolygonGeometry => Boolean(geometry));
  }, [conflicts, features, farmerFields]);

  useEffect(() => {
    overlapRef.current?.remove();
    overlapRef.current = null;
    if (!draft.geometry || conflictGeometries.length === 0) return;

    const group = L.layerGroup().addTo(map);
    overlapRef.current = group;
    for (const other of conflictGeometries) {
      try {
        const shared = intersect({
          type: 'FeatureCollection',
          features: [
            { type: 'Feature', properties: {}, geometry: draft.geometry },
            { type: 'Feature', properties: {}, geometry: other },
          ],
        });
        if (shared) {
          L.geoJSON(shared, { style: OVERLAP_STYLE, interactive: false }).addTo(group);
        }
      } catch {
        // A shape turf cannot intersect still fails validation server-side, which is
        // what actually blocks the save; the highlight is a courtesy.
      }
    }
    return () => {
      group.remove();
    };
  }, [map, draft.geometry, conflictGeometries]);

  /* The imperative handle the toolbar calls. */
  useEffect(() => {
    const handle: FieldMapHandle = {
      startDraw: () => {
        clearLayer();
        emit(null, null);
        drawingRef.current = true;
        setTool('draw');
        onToolChange({ drawing: true, editing: false });
        map.pm.enableDraw('Polygon');
      },
      cancelDraw: () => {
        map.pm.disableDraw();
        drawingRef.current = false;
        setTool('idle');
        onToolChange({ drawing: false, editing: false });
      },
      toggleEdit: () => {
        const layer = layerRef.current;
        if (!layer?.pm) return;
        if (layer.pm.enabled()) {
          layer.pm.disable();
          editingRef.current = false;
          setTool('idle');
        } else {
          layer.pm.enable({ allowSelfIntersection: false });
          editingRef.current = true;
          setTool('edit');
        }
        onToolChange({ drawing: false, editing: editingRef.current });
      },
      startPin: () => {
        pinningRef.current = true;
        setTool('pin');
        map.getContainer().classList.add('geoman-draw-cursor');
      },
      deleteDraft: () => {
        clearLayer();
        emit(null, null);
        setTool('idle');
        onToolChange({ drawing: false, editing: false });
      },
      undoVertex: () => {
        if (drawingRef.current) {
          // Geoman exposes this only on the draw instance, not in its public typings.
          const shape = map.pm.Draw.Polygon as unknown as GeomanDrawShape;
          shape._removeLastVertex?.();
          return;
        }
        const layer = layerRef.current;
        const geometry = layer ? toPolygonGeometry(layer) : null;
        const ring = geometry?.coordinates[0];
        if (!ring || ring.length <= 5) return; // a triangle is the smallest valid field
        const reduced = ring.slice(0, -2).concat([ring[0] as number[]]);
        emit({ type: 'Polygon', coordinates: [reduced] }, draft.pin);
      },
      flyTo: (lat, lng, zoom) => {
        map.flyTo([lat, lng], zoom ?? map.getZoom(), { duration: 0.6 });
      },
      fitField: (field) => {
        const [minLng, minLat, maxLng, maxLat] = field.bbox as [number, number, number, number];
        map.flyToBounds(
          [
            [minLat, minLng],
            [maxLat, maxLng],
          ],
          { padding: [48, 48], maxZoom: 20, duration: 0.6 },
        );
      },
      fitAllFields: () => {
        const points: [number, number][] = [];
        for (const f of farmerFields) {
          const [minLng, minLat, maxLng, maxLat] = f.bbox as [number, number, number, number];
          points.push([minLat, minLng], [maxLat, maxLng]);
        }
        if (points.length === 0) {
          for (const feat of features) {
            points.push([feat.pin_lat, feat.pin_lng]);
          }
        }
        if (points.length > 0) {
          map.flyToBounds(L.latLngBounds(points), { padding: [48, 48], maxZoom: 19, duration: 0.6 });
        }
      },
      invalidate: () => {
        window.setTimeout(() => map.invalidateSize(), 120);
      },
    };
    handleRef.current = handle;
    return () => {
      handleRef.current = null;
    };
  }, [map, handleRef, clearLayer, emit, setTool, onToolChange, draft.pin, farmerFields, features]);

  useEffect(
    () => () => {
      clearLayer();
      overlapRef.current?.remove();
      pinRef.current?.remove();
    },
    [clearLayer],
  );

  return null;
}

/* -------------------------------------------------------------------------- */
/* The map                                                                     */
/* -------------------------------------------------------------------------- */

export function FieldMap({
  farmerId,
  farmerName,
  farmerSawieId,
  country,
  farmerFields,
  editingFieldId,
  draft,
  onDraftChange,
  conflicts,
  position,
  selectedFieldId,
  onSelectField,
  handleRef,
  onToolChange,
}: FieldMapProps) {
  const baseLayer = useMapStore((s) => s.baseLayer);
  const showLabels = useMapStore((s) => s.showLabels);
  const [features, setFeatures] = useState<MapFeature[]>([]);

  // Never fall back to another farmer's field here: a new farmer must open on their
  // own position or their region, not on somebody else's plot.
  const centre = useMemo(() => {
    const first = farmerFields[0];
    if (first) return { lat: first.pin_lat, lng: first.pin_lng, zoom: DEFAULT_ZOOM };
    if (position) return { lat: position.lat, lng: position.lng, zoom: DEFAULT_ZOOM };
    return REGION_CENTRES[country] ?? { lat: 30.1575, lng: 71.5249, zoom: DEFAULT_ZOOM };
  }, [position, farmerFields, country]);

  const layers = useTileLayers();
  const base = baseLayer === 'street' ? layers.street : layers.satellite;
  const onFeatures = useCallback((next: MapFeature[]) => setFeatures(next), []);

  return (
    <MapContainer
      center={[centre.lat, centre.lng]}
      zoom={centre.zoom}
      minZoom={4}
      maxZoom={22}
      scrollWheelZoom
      preferCanvas
      className="h-full w-full"
      attributionControl
    >
      <MapResizeHandler />
      <CentreOnPosition
        position={position}
        enabled={farmerFields.length === 0 && !editingFieldId}
      />
      <TileLayer
        key={base.id}
        url={base.url}
        attribution={base.attribution}
        maxZoom={22}
        tileSize={base.tileSize ?? 512}
        zoomOffset={base.zoomOffset ?? -1}
        updateWhenZooming={false}
        updateWhenIdle
      />
      {showLabels && (
        <TileLayer
          url={layers.labels.url}
          attribution={layers.labels.attribution}
          maxZoom={22}
          maxNativeZoom={19}
          updateWhenZooming={false}
          updateWhenIdle
        />
      )}
      <AllFieldsLayer
        farmerId={farmerId}
        farmerName={farmerName}
        farmerSawieId={farmerSawieId}
        country={country}
        farmerFields={farmerFields}
        editingFieldId={editingFieldId}
        selectedFieldId={selectedFieldId}
        onSelectField={onSelectField}
        onFeatures={onFeatures}
      />
      <PositionLayer position={position} />
      <DraftLayer
        draft={draft}
        onDraftChange={onDraftChange}
        conflicts={conflicts}
        features={features}
        farmerFields={farmerFields}
        handleRef={handleRef}
        onToolChange={onToolChange}
      />
    </MapContainer>
  );
}

export { GEOMETRY_ZOOM };
