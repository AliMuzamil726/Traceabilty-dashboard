import {
  Crosshair,
  Layers,
  Maximize,
  MapPin,
  Minimize,
  PenLine,
  Pencil,
  Trash2,
  Undo2,
  X,
} from 'lucide-react';
import { Button } from '@/design-system/components/Button';
import { IconButton } from '@/design-system/components/IconButton';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { cn } from '@/core/utils/cn';
import { BASE_LAYERS, type BaseLayerId } from '../map/tileLayers';
import { useMapStore } from '../store/mapStore';

export interface MapToolbarProps {
  hasDraft: boolean;
  drawing: boolean;
  editing: boolean;
  fullscreen: boolean;
  locating: boolean;
  onDraw: () => void;
  onCancelDraw: () => void;
  onEdit: () => void;
  onPin: () => void;
  onDelete: () => void;
  onUndo: () => void;
  onLocate: () => void;
  onFullscreen: () => void;
  className?: string;
}

/**
 * The map's controls, built from design-system components rather than Leaflet's own.
 *
 * Geoman ships a toolbar of its own; it is hidden in map.css and this drives it through
 * the API instead, so the controls match every other button in the product and stay
 * keyboard accessible with real labels.
 */
export function MapToolbar({
  hasDraft,
  drawing,
  editing,
  fullscreen,
  locating,
  onDraw,
  onCancelDraw,
  onEdit,
  onPin,
  onDelete,
  onUndo,
  onLocate,
  onFullscreen,
  className,
}: MapToolbarProps) {
  const baseLayer = useMapStore((s) => s.baseLayer);
  const setBaseLayer = useMapStore((s) => s.setBaseLayer);
  const showLabels = useMapStore((s) => s.showLabels);
  const toggleLabels = useMapStore((s) => s.toggleLabels);
  const showAllFields = useMapStore((s) => s.showAllFields);
  const toggleAllFields = useMapStore((s) => s.toggleAllFields);

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-2 rounded-card border border-line bg-surface p-2 shadow-1',
        className,
      )}
      role="toolbar"
      aria-label="Map tools"
    >
      {drawing ? (
        <Button variant="secondary" size="sm" leftIcon={<X className="h-4 w-4" />} onClick={onCancelDraw}>
          Cancel drawing
        </Button>
      ) : (
        <Button
          size="sm"
          leftIcon={<PenLine className="h-4 w-4" />}
          onClick={onDraw}
          disabled={hasDraft}
        >
          Draw polygon
        </Button>
      )}

      <Button
        variant="secondary"
        size="sm"
        leftIcon={<Pencil className="h-4 w-4" />}
        onClick={onEdit}
        disabled={!hasDraft || drawing}
      >
        {editing ? 'Stop editing' : 'Edit vertices'}
      </Button>

      <Button
        variant="secondary"
        size="sm"
        leftIcon={<MapPin className="h-4 w-4" />}
        onClick={onPin}
        disabled={!hasDraft || drawing}
      >
        Place pin
      </Button>

      <Button
        variant="secondary"
        size="sm"
        leftIcon={<Undo2 className="h-4 w-4" />}
        onClick={onUndo}
        disabled={!drawing && !hasDraft}
      >
        Undo last vertex
      </Button>

      <Button
        variant="secondary"
        size="sm"
        leftIcon={<Trash2 className="h-4 w-4" />}
        onClick={onDelete}
        disabled={!hasDraft}
      >
        Delete shape
      </Button>

      <span className="mx-1 hidden h-6 w-px bg-line sm:block" aria-hidden />

      <SegmentedControl
        size="sm"
        aria-label="Base map"
        value={baseLayer}
        onChange={(value: BaseLayerId) => setBaseLayer(value)}
        options={BASE_LAYERS.map((layer) => ({
          value: layer.id as BaseLayerId,
          label: layer.label,
        }))}
      />

      <Button
        variant={showLabels ? 'primary' : 'secondary'}
        size="sm"
        leftIcon={<Layers className="h-4 w-4" />}
        onClick={toggleLabels}
        aria-pressed={showLabels}
      >
        Labels
      </Button>

      <Button
        variant={showAllFields ? 'primary' : 'secondary'}
        size="sm"
        onClick={toggleAllFields}
        aria-pressed={showAllFields}
      >
        Other fields
      </Button>

      <span className="ml-auto flex items-center gap-2">
        <IconButton
          label="Locate me"
          variant="secondary"
          size="sm"
          icon={<Crosshair className={cn('h-4 w-4', locating && 'animate-spin')} />}
          onClick={onLocate}
        />
        <IconButton
          label={fullscreen ? 'Leave fullscreen' : 'Fullscreen'}
          variant="secondary"
          size="sm"
          icon={fullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
          onClick={onFullscreen}
        />
      </span>
    </div>
  );
}
