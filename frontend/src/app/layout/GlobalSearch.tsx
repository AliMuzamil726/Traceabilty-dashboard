import { useQuery } from '@tanstack/react-query';
import { MapPin, Search, User } from 'lucide-react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/core/api/client';
import type { Page } from '@/core/api/types';
import { cn } from '@/core/utils/cn';

interface FarmerHit {
  id: string;
  sawie_id: number;
  name: string;
  crop: string;
  location_summary: string;
  field_count: number;
}

interface Result {
  key: string;
  kind: 'farmer' | 'field';
  title: string;
  detail: string;
  to: string;
}

/** A field ID is the farmer's SAWIE ID and a sequence, e.g. 1001-03. */
const FIELD_ID = /^(\d{1,9})-(\d{1,4})$/;

function useDebounced(value: string, ms = 250): string {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Top-bar search: a farmer by SAWIE ID or name, or a field by its field ID. */
export function GlobalSearch({ className }: { className?: string }) {
  const navigate = useNavigate();
  const listId = `gs${useId().replace(/:/g, '')}`;
  const boxRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const term = useDebounced(text.trim());
  const field = FIELD_ID.exec(term);
  const q = field ? field[1]! : term;

  const search = useQuery({
    queryKey: ['global-search', q],
    queryFn: ({ signal }) => api.get<Page<FarmerHit>>('/v1/register/farmers', { q, page: 1, page_size: 8 }, signal),
    enabled: q.length >= 1,
    staleTime: 30_000,
  });

  const results: Result[] = (search.data?.items ?? []).flatMap((f): Result[] => {
    const farmer: Result = {
      key: `f-${f.id}`,
      kind: 'farmer',
      title: `${f.sawie_id} · ${f.name}`,
      detail: [f.crop === 'cotton' ? 'Cotton' : 'Hemp', f.location_summary, `${f.field_count} field${f.field_count === 1 ? '' : 's'}`].filter(Boolean).join(' · '),
      to: `/register/farmers/${f.id}`,
    };
    if (field && String(f.sawie_id) === field[1]) {
      return [{ key: `fl-${f.id}`, kind: 'field', title: `Field ${term}`, detail: `${f.name} · SAWIE ID ${f.sawie_id}`, to: `/register/farmers/${f.id}` }, farmer];
    }
    return [farmer];
  });

  useEffect(() => setActive(0), [term]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  const go = (r: Result) => {
    setOpen(false);
    setText('');
    navigate(r.to);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && results[active]) {
      e.preventDefault();
      go(results[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const showList = open && term.length > 0;

  return (
    <div ref={boxRef} className={cn('relative', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-label="Search by SAWIE ID, name, phone number or field ID"
        placeholder="SAWIE ID, name, phone or field ID"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        className="h-9 w-full rounded-control border border-line bg-canvas pl-9 pr-3 text-base text-ink placeholder:text-muted focus:border-forest-500 focus:bg-surface focus:outline-none"
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-control border border-line bg-surface py-1 shadow-2"
        >
          {search.isFetching && results.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted">Searching</li>
          ) : results.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted">No match</li>
          ) : (
            results.map((r, i) => {
              const Icon = r.kind === 'field' ? MapPin : User;
              return (
                <li
                  key={r.key}
                  role="option"
                  aria-selected={i === active}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    go(r);
                  }}
                  className={cn('flex cursor-pointer items-start gap-2.5 px-3 py-2', i === active && 'bg-forest-50')}
                >
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-ink">{r.title}</span>
                    <span className="block truncate text-xs text-muted">{r.detail}</span>
                  </span>
                </li>
              );
            })
          )}
        </ul>
      )}
    </div>
  );
}
