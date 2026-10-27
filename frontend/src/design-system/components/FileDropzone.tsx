import { UploadCloud } from 'lucide-react';
import { useId, useRef, useState, type DragEvent } from 'react';
import { cn } from '@/core/utils/cn';

export interface FileDropzoneProps {
  onFiles: (files: File[]) => void;
  /** e.g. "image/*" or ".jpg,.png" */
  accept?: string;
  multiple?: boolean;
  /** Maximum size per file in bytes. Larger files are rejected with `onReject`. */
  maxSize?: number;
  onReject?: (file: File, reason: 'too_large' | 'wrong_type') => void;
  label?: string;
  hint?: string;
  disabled?: boolean;
  invalid?: boolean;
}

function matchesAccept(file: File, accept?: string): boolean {
  if (!accept) return true;
  return accept.split(',').some((rule) => {
    const r = rule.trim().toLowerCase();
    if (r.startsWith('.')) return file.name.toLowerCase().endsWith(r);
    if (r.endsWith('/*')) return file.type.toLowerCase().startsWith(r.slice(0, -1));
    return file.type.toLowerCase() === r;
  });
}

/** Drag-and-drop area that is also a regular, keyboard-operable file button. */
export function FileDropzone({ onFiles, accept, multiple, maxSize, onReject, label = 'Add files', hint, disabled, invalid }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const hintId = `dz${useId().replace(/:/g, '')}`;

  const handle = (list: FileList | null) => {
    if (!list) return;
    const accepted: File[] = [];
    for (const file of Array.from(list)) {
      if (!matchesAccept(file, accept)) onReject?.(file, 'wrong_type');
      else if (maxSize && file.size > maxSize) onReject?.(file, 'too_large');
      else accepted.push(file);
    }
    if (accepted.length) onFiles(multiple ? accepted : accepted.slice(0, 1));
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!disabled) handle(e.dataTransfer.files);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        'rounded-card border border-dashed transition-colors duration-fast ease-brand',
        dragging ? 'border-forest-600 bg-forest-50' : invalid ? 'border-danger bg-surface' : 'border-line bg-surface hover:border-forest-500/50',
        disabled && 'opacity-50',
      )}
    >
      <button
        type="button"
        disabled={disabled}
        aria-describedby={hint ? hintId : undefined}
        onClick={() => inputRef.current?.click()}
        className="flex w-full flex-col items-center gap-2 rounded-card px-6 py-8 text-center disabled:cursor-not-allowed"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-control bg-forest-50 text-forest-700" aria-hidden>
          <UploadCloud className="h-5 w-5" />
        </span>
        <span className="font-medium text-ink">{label}</span>
        <span className="text-sm text-muted">Drag files here or choose them from this device</span>
        {hint && (
          <span id={hintId} className="text-xs text-muted">
            {hint}
          </span>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        accept={accept}
        multiple={multiple}
        onChange={(e) => {
          handle(e.target.files);
          e.target.value = '';
        }}
      />
    </div>
  );
}
