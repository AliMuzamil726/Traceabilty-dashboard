import { ChevronRight, GitMerge, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/core/utils/cn';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { IconButton } from '@/design-system/components/IconButton';
import type { LocationNode, LocationTree as Tree } from '../api/types';

export interface LocationTreeProps {
  tree: Tree;
  onAdd: (parent: LocationNode | null, level: string) => void;
  onRename: (node: LocationNode) => void;
  onDelete: (node: LocationNode) => void;
  onMerge: (node: LocationNode) => void;
}

/**
 * Country, province, district, tehsil as a tree (and postcode area to county for the UK).
 *
 * The usage count sits next to every place, because a farmer stores the place by name:
 * renaming one here moves every farmer that names it, and that number is what makes
 * the size of the change obvious before it is made.
 */
export function LocationTree({ tree, onAdd, onRename, onDelete, onMerge }: LocationTreeProps) {
  const topLevel = tree.levels[0] ?? 'province';
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          {tree.levels.map((level) => tree.labels[level] ?? level).join(' > ')}
        </p>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAdd(null, topLevel)}
          leftIcon={<Plus className="h-4 w-4" aria-hidden />}
        >
          Add {(tree.labels[topLevel] ?? topLevel).toLowerCase()}
        </Button>
      </div>

      <ul className="rounded-card border border-line">
        {tree.items.map((node) => (
          <TreeRow
            key={node.id}
            node={node}
            tree={tree}
            depth={0}
            onAdd={onAdd}
            onRename={onRename}
            onDelete={onDelete}
            onMerge={onMerge}
          />
        ))}
      </ul>
    </div>
  );
}

interface RowProps extends Omit<LocationTreeProps, 'tree'> {
  node: LocationNode;
  tree: Tree;
  depth: number;
}

function TreeRow({ node, tree, depth, onAdd, onRename, onDelete, onMerge }: RowProps) {
  const [open, setOpen] = useState(depth === 0);
  const hasChildren = node.children.length > 0;
  const childLevel = tree.levels[tree.levels.indexOf(node.level) + 1];

  return (
    <li className="border-b border-line last:border-b-0">
      <div
        className="flex flex-wrap items-center gap-2 px-3 py-2"
        style={{ paddingLeft: `${12 + depth * 20}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="rounded-control p-0.5 text-muted hover:bg-canvas"
          >
            <ChevronRight
              className={cn('h-4 w-4 transition-transform duration-fast', open && 'rotate-90')}
              aria-hidden
            />
            <span className="sr-only">
              {open ? 'Hide' : 'Show'} places inside {node.name}
            </span>
          </button>
        ) : (
          <span className="w-5" aria-hidden />
        )}

        <span className={cn('min-w-0 flex-1 truncate text-base', !node.active && 'text-muted')}>
          {node.name}
          {!node.active && <span className="ml-2 text-sm">(hidden from new forms)</span>}
        </span>

        {node.usage > 0 && (
          <Badge tone="neutral">
            {node.usage} farmer{node.usage === 1 ? '' : 's'}
          </Badge>
        )}

        <span className="flex items-center gap-0.5">
          {childLevel && (
            <IconButton
              label={`Add a ${(tree.labels[childLevel] ?? childLevel).toLowerCase()} in ${node.name}`}
              icon={<Plus className="h-4 w-4" />}
              onClick={() => onAdd(node, childLevel)}
            />
          )}
          <IconButton
            label={`Rename ${node.name}`}
            icon={<Pencil className="h-4 w-4" />}
            onClick={() => onRename(node)}
          />
          <IconButton
            label={`Merge ${node.name} into another place`}
            icon={<GitMerge className="h-4 w-4" />}
            onClick={() => onMerge(node)}
          />
          <IconButton
            label={`Delete ${node.name}`}
            icon={<Trash2 className="h-4 w-4" />}
            onClick={() => onDelete(node)}
          />
        </span>
      </div>

      {open && hasChildren && (
        <ul>
          {node.children.map((child) => (
            <TreeRow
              key={child.id}
              node={child}
              tree={tree}
              depth={depth + 1}
              onAdd={onAdd}
              onRename={onRename}
              onDelete={onDelete}
              onMerge={onMerge}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
