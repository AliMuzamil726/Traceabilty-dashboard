import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/design-system/components/Button';
import { Drawer } from '@/design-system/components/Dialog';
import { toast } from '@/design-system/components/toastStore';
import type { Field } from '../api/types';
import { formatLatLng } from '../format';

export interface VertexDrawerProps {
  field: Field | null;
  open: boolean;
  onClose: () => void;
}

/** Vertices as [lng, lat] pairs, less the repeated closing point. */
function vertices(field: Field): Array<{ lat: number; lng: number }> {
  const ring = field.geometry.coordinates[0] ?? [];
  const open = ring.length > 1 ? ring.slice(0, -1) : ring;
  return open.map((pair) => ({ lng: pair[0] ?? 0, lat: pair[1] ?? 0 }));
}

async function copy(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Every corner of a field, to six decimal places.
 *
 * Six decimals is about 0.1 m at these latitudes, which is finer than any boundary
 * walked with a phone, so it is enough to reproduce the shape exactly elsewhere.
 * Each row copies on its own, and the whole list copies as CSV for a report.
 */
export function VertexDrawer({ field, open, onClose }: VertexDrawerProps) {
  const [copied, setCopied] = useState<number | null>(null);

  if (!field) return null;
  const points = vertices(field);

  const copyOne = async (index: number, lat: number, lng: number) => {
    const ok = await copy(formatLatLng(lat, lng));
    if (ok) {
      setCopied(index);
      window.setTimeout(() => setCopied(null), 1500);
    } else {
      toast.error('Could not copy', 'This browser blocked clipboard access.');
    }
  };

  const copyAll = async () => {
    const csv = ['n,latitude,longitude']
      .concat(points.map((p, i) => `${i + 1},${p.lat.toFixed(6)},${p.lng.toFixed(6)}`))
      .join('\n');
    if (await copy(csv)) toast.success('Vertices copied', `${points.length} corners as CSV.`);
    else toast.error('Could not copy', 'This browser blocked clipboard access.');
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={`Corners of field ${field.field_id}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button leftIcon={<Copy className="h-4 w-4" />} onClick={copyAll}>
            Copy all as CSV
          </Button>
        </>
      }
    >
      <div className="px-5 py-4">
        <p className="text-base text-muted">
          {points.length} corners, to six decimal places.
        </p>
        <table className="mt-3 w-full border-collapse text-base">
          <caption className="sr-only">
            Every corner of field {field.field_id} with its latitude and longitude
          </caption>
          <thead>
            <tr className="border-b border-line text-sm text-muted">
              <th scope="col" className="py-2 text-left font-medium">
                #
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                Latitude
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                Longitude
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                <span className="sr-only">Copy</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {points.map((point, index) => (
              <tr key={`${point.lat}-${point.lng}-${index}`} className="border-b border-line last:border-b-0">
                <td className="py-2 tabular text-muted">{index + 1}</td>
                <td className="mono-id py-2 text-right text-sm text-ink">{point.lat.toFixed(6)}</td>
                <td className="mono-id py-2 text-right text-sm text-ink">{point.lng.toFixed(6)}</td>
                <td className="py-2 text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    leftIcon={
                      copied === index ? (
                        <Check className="h-3.5 w-3.5" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )
                    }
                    onClick={() => void copyOne(index, point.lat, point.lng)}
                  >
                    {copied === index ? 'Copied' : 'Copy'}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Drawer>
  );
}
