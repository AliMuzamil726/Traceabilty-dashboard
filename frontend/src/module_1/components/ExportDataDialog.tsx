import { useQueries, useQuery } from '@tanstack/react-query';
import {
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Download,
  FileJson,
  FileSpreadsheet,
  Search,
  ShieldCheck,
  Square,
  UserCheck,
  UserCog,
  Users,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { cn } from '@/core/utils/cn';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Dialog } from '@/design-system/components/Dialog';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { Skeleton } from '@/design-system/components/Skeleton';
import { toast } from '@/design-system/components/toastStore';
import { fieldbookApi, fieldbookKeys } from '@/module_3';
import type { FarmerOption, OfficerOption } from '@/module_3';
import { settingsApi, settingsKeys } from '@/module_8';
import type { Officer } from '@/module_8';
import type { CropFilter } from '../api/types';

export interface ExportDataDialogProps {
  open: boolean;
  onClose: () => void;
  seasonYear: number;
  cropFilter: CropFilter;
}

type ExportFormat = 'csv' | 'json';
type Group = 'farmers' | 'officers' | 'staff' | 'admins';

const GROUPS: { key: Group; label: string }[] = [
  { key: 'farmers', label: 'Farmers' },
  { key: 'officers', label: 'Field officers' },
  { key: 'staff', label: 'Staff' },
  { key: 'admins', label: 'Administrators' },
];

const RECORD_TYPE = {
  farmer: 'Farmer',
  officer: 'Field officer',
  staff: 'Staff',
  admin: 'Administrator',
} as const;

interface ExportRow {
  record_type: string;
  name: string;
  code: string;
  field_office: string;
  country: string;
  field_officer: string;
  crop: string;
  season_year: number | '';
  mapped_fields: number | '';
  fieldbooks_draft: number | '';
  fieldbooks_submitted: number | '';
  traceability_status: string;
}

const CSV_COLUMNS: { header: string; key: keyof ExportRow }[] = [
  { header: 'Record Type', key: 'record_type' },
  { header: 'Name', key: 'name' },
  { header: 'Code / SAWIE ID', key: 'code' },
  { header: 'Field Office', key: 'field_office' },
  { header: 'Country', key: 'country' },
  { header: 'Field Officer', key: 'field_officer' },
  { header: 'Crop Programme', key: 'crop' },
  { header: 'Season Year', key: 'season_year' },
  { header: 'Mapped Fields', key: 'mapped_fields' },
  { header: 'Draft Fieldbooks', key: 'fieldbooks_draft' },
  { header: 'Submitted Fieldbooks', key: 'fieldbooks_submitted' },
  { header: 'Traceability Status', key: 'traceability_status' },
];

function escapeCsvCell(value: string | number | null | undefined): string {
  const str = value == null ? '' : String(value);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Export Data modal. Pick what to export (farmers, field officers, staff, administrators),
 * then tick the people. Field officers expand to their farmers.
 */
export function ExportDataDialog({ open, onClose, seasonYear, cropFilter }: ExportDataDialogProps) {
  const [search, setSearch] = useState('');
  const [format, setFormat] = useState<ExportFormat>('csv');
  const [include, setInclude] = useState<Record<Group, boolean>>({
    farmers: true,
    officers: true,
    staff: true,
    admins: true,
  });
  const [expandedOfficers, setExpandedOfficers] = useState<Record<string, boolean>>({});
  const [selectedFarmers, setSelectedFarmers] = useState<Record<string, boolean>>({});
  const [selectedPeople, setSelectedPeople] = useState<Record<string, boolean>>({});
  const [initialized, setInitialized] = useState(false);

  const officersQuery = useQuery({
    queryKey: fieldbookKeys.officers,
    queryFn: ({ signal }) => fieldbookApi.officers(signal),
    enabled: open,
  });

  // Staff and administrators come from the people list in Settings. Only administrators may
  // read it, so a refusal just leaves those two groups empty.
  const peopleQuery = useQuery({
    queryKey: settingsKeys.officers({ active: true }),
    queryFn: ({ signal }) => settingsApi.officers({ active: true }, signal),
    enabled: open,
    retry: false,
  });

  const officers: OfficerOption[] = useMemo(
    () => (officersQuery.data ?? []).filter((o) => o.role === 'officer' || o.role === undefined),
    [officersQuery.data],
  );
  const staff: Officer[] = useMemo(
    () => (peopleQuery.data ?? []).filter((p) => p.role === 'staff'),
    [peopleQuery.data],
  );
  const admins: Officer[] = useMemo(
    () => (peopleQuery.data ?? []).filter((p) => p.role === 'admin'),
    [peopleQuery.data],
  );

  const farmerQueries = useQueries({
    queries: officers.map((officer) => ({
      queryKey: fieldbookKeys.farmers(officer.id, '', seasonYear),
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        fieldbookApi.farmers(officer.id, undefined, seasonYear, signal),
      enabled: open && officers.length > 0,
      staleTime: 60_000,
    })),
  });

  const loadingFarmers = farmerQueries.some((q) => q.isLoading);
  const loading = officersQuery.isLoading || loadingFarmers;

  const farmersByOfficer = useMemo(() => {
    const map = new Map<string, FarmerOption[]>();
    officers.forEach((officer, index) => {
      const list = farmerQueries[index]?.data ?? [];
      map.set(officer.id, cropFilter === 'all' ? list : list.filter((f) => f.crop === cropFilter));
    });
    return map;
  }, [officers, farmerQueries, cropFilter]);

  // Everything starts ticked.
  useEffect(() => {
    if (!open) {
      setInitialized(false);
      return;
    }
    if (initialized || loading || peopleQuery.isLoading || officers.length === 0) return;
    const farmers: Record<string, boolean> = {};
    const people: Record<string, boolean> = {};
    for (const officer of officers) {
      people[officer.id] = true;
      for (const farmer of farmersByOfficer.get(officer.id) ?? []) farmers[farmer.id] = true;
    }
    for (const person of [...staff, ...admins]) people[person.id] = true;
    setSelectedFarmers(farmers);
    setSelectedPeople(people);
    setExpandedOfficers({});
    setInitialized(true);
  }, [open, initialized, loading, peopleQuery.isLoading, officers, farmersByOfficer, staff, admins]);

  const q = search.trim().toLowerCase();
  const matchesPerson = (p: { full_name: string; code: string; field_office_name: string | null }) =>
    !q ||
    p.full_name.toLowerCase().includes(q) ||
    p.code.toLowerCase().includes(q) ||
    (p.field_office_name ?? '').toLowerCase().includes(q);

  const showTree = include.officers || include.farmers;

  const filteredTree = useMemo(() => {
    return officers
      .map((officer) => {
        const all = farmersByOfficer.get(officer.id) ?? [];
        if (!q) return { officer, farmers: all, keep: true };
        const officerMatches = matchesPerson(officer);
        const farmers = officerMatches
          ? all
          : all.filter((f) => f.name.toLowerCase().includes(q) || String(f.sawie_id).includes(q));
        return { officer, farmers, keep: officerMatches || farmers.length > 0 };
      })
      .filter((entry) => entry.keep);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [officers, farmersByOfficer, q]);

  const visibleStaff = staff.filter(matchesPerson);
  const visibleAdmins = admins.filter(matchesPerson);

  const totalFarmers = useMemo(
    () => officers.reduce((n, o) => n + (farmersByOfficer.get(o.id) ?? []).length, 0),
    [officers, farmersByOfficer],
  );
  const pickedFarmers = include.farmers
    ? officers.reduce(
        (n, o) => n + (farmersByOfficer.get(o.id) ?? []).filter((f) => selectedFarmers[f.id]).length,
        0,
      )
    : 0;
  const pickedOfficers = include.officers ? officers.filter((o) => selectedPeople[o.id]).length : 0;
  const pickedStaff = include.staff ? staff.filter((p) => selectedPeople[p.id]).length : 0;
  const pickedAdmins = include.admins ? admins.filter((p) => selectedPeople[p.id]).length : 0;
  const pickedTotal = pickedFarmers + pickedOfficers + pickedStaff + pickedAdmins;

  const toggleGroup = (key: Group) => setInclude((prev) => ({ ...prev, [key]: !prev[key] }));

  const toggleAll = (checked: boolean) => {
    const farmers: Record<string, boolean> = {};
    const people: Record<string, boolean> = {};
    for (const officer of officers) {
      people[officer.id] = checked;
      for (const farmer of farmersByOfficer.get(officer.id) ?? []) farmers[farmer.id] = checked;
    }
    for (const person of [...staff, ...admins]) people[person.id] = checked;
    setSelectedFarmers(farmers);
    setSelectedPeople(people);
  };

  const toggleOfficer = (officerId: string) => {
    const next = !selectedPeople[officerId];
    setSelectedPeople((prev) => ({ ...prev, [officerId]: next }));
    setSelectedFarmers((prev) => {
      const copy = { ...prev };
      for (const farmer of farmersByOfficer.get(officerId) ?? []) copy[farmer.id] = next;
      return copy;
    });
  };

  const togglePerson = (id: string) => setSelectedPeople((prev) => ({ ...prev, [id]: !prev[id] }));
  const toggleFarmer = (id: string) => setSelectedFarmers((prev) => ({ ...prev, [id]: !prev[id] }));
  const toggleExpand = (id: string) => setExpandedOfficers((prev) => ({ ...prev, [id]: !prev[id] }));

  const handleExport = () => {
    const rows: ExportRow[] = [];
    const blank = { crop: '', season_year: '' as const, mapped_fields: '' as const, fieldbooks_draft: '' as const, fieldbooks_submitted: '' as const, traceability_status: '' };

    if (include.officers) {
      for (const o of officers) {
        if (!selectedPeople[o.id]) continue;
        rows.push({
          record_type: RECORD_TYPE.officer,
          name: o.full_name,
          code: o.code,
          field_office: o.field_office_name ?? '-',
          country: o.country,
          field_officer: '',
          ...blank,
        });
      }
    }
    if (include.farmers) {
      for (const o of officers) {
        for (const f of farmersByOfficer.get(o.id) ?? []) {
          if (!selectedFarmers[f.id]) continue;
          rows.push({
            record_type: RECORD_TYPE.farmer,
            name: f.name,
            code: String(f.sawie_id),
            field_office: o.field_office_name ?? '-',
            country: o.country,
            field_officer: o.full_name,
            crop: String(f.crop),
            season_year: seasonYear,
            mapped_fields: f.field_count,
            fieldbooks_draft: f.drafts,
            fieldbooks_submitted: f.submitted,
            traceability_status: String(f.fieldbook_status).replace(/_/g, ' '),
          });
        }
      }
    }
    const addPeople = (list: Officer[], type: string) => {
      for (const p of list) {
        if (!selectedPeople[p.id]) continue;
        rows.push({
          record_type: type,
          name: p.full_name,
          code: p.code,
          field_office: p.field_office_name ?? '-',
          country: p.country,
          field_officer: '',
          ...blank,
        });
      }
    };
    if (include.staff) addPeople(staff, RECORD_TYPE.staff);
    if (include.admins) addPeople(admins, RECORD_TYPE.admin);

    if (rows.length === 0) {
      toast.warning('Nothing selected', 'Tick at least one person to export.');
      return;
    }

    const timestamp = new Date().toISOString().slice(0, 10);
    const filename = `sawie-export-${seasonYear}-${timestamp}.${format}`;

    let content: string;
    let mime: string;
    if (format === 'csv') {
      mime = 'text/csv;charset=utf-8;';
      content = [
        CSV_COLUMNS.map((c) => c.header).join(','),
        ...rows.map((r) => CSV_COLUMNS.map((c) => escapeCsvCell(r[c.key])).join(',')),
      ].join('\n');
    } else {
      mime = 'application/json;charset=utf-8;';
      content = JSON.stringify(
        {
          exported_at: new Date().toISOString(),
          season_year: seasonYear,
          crop_filter: cropFilter,
          counts: { farmers: pickedFarmers, field_officers: pickedOfficers, staff: pickedStaff, administrators: pickedAdmins },
          records: rows,
        },
        null,
        2,
      );
    }

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);

    toast.success('Export complete', `Exported ${rows.length} record${rows.length === 1 ? '' : 's'}.`);
    onClose();
  };

  const summary = [
    include.farmers && `${pickedFarmers} of ${totalFarmers} farmers`,
    include.officers && `${pickedOfficers} field officers`,
    include.staff && `${pickedStaff} staff`,
    include.admins && `${pickedAdmins} admins`,
  ].filter(Boolean);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Export Data"
      description="Choose what to export, then tick the people to include."
      size="lg"
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-muted">
            {summary.length > 0 ? summary.join(' · ') : 'Nothing chosen'}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button leftIcon={<Download className="h-4 w-4" />} disabled={pickedTotal === 0} onClick={handleExport}>
              Export {pickedTotal > 0 ? `(${pickedTotal})` : ''}
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        {/* What to export */}
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="What to export">
          <span className="text-sm font-medium text-ink">Export:</span>
          {GROUPS.map((g) => (
            <button
              key={g.key}
              type="button"
              aria-pressed={include[g.key]}
              onClick={() => toggleGroup(g.key)}
              className={cn(
                'rounded-pill border px-3 py-1 text-sm transition-colors',
                include[g.key]
                  ? 'border-forest-600 bg-forest-50 font-medium text-forest-800'
                  : 'border-line bg-surface text-muted hover:bg-canvas',
              )}
            >
              {g.label}
            </button>
          ))}
        </div>

        {/* Search, bulk actions, format */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-canvas p-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, code, office or SAWIE ID"
              aria-label="Filter people"
              className="h-9 w-full rounded-control border border-line bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-muted focus:border-forest-500 focus:outline-none"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="secondary" size="sm" leftIcon={<CheckSquare className="h-3.5 w-3.5" />} onClick={() => toggleAll(true)}>
              Select all
            </Button>
            <Button type="button" variant="secondary" size="sm" leftIcon={<Square className="h-3.5 w-3.5" />} onClick={() => toggleAll(false)}>
              Clear all
            </Button>
            <SegmentedControl
              aria-label="Export file format"
              size="sm"
              value={format}
              onChange={setFormat}
              options={[
                { value: 'csv', label: 'CSV' },
                { value: 'json', label: 'JSON' },
              ]}
            />
          </div>
        </div>

        <div className="max-h-[min(360px,calc(100dvh-26rem))] min-h-[140px] divide-y divide-line overflow-y-auto rounded-card border border-line bg-surface">
          {loading || peopleQuery.isLoading ? (
            <div className="flex flex-col gap-3 p-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !showTree && !include.staff && !include.admins ? (
            <div className="p-8 text-center text-sm text-muted">Choose something to export above.</div>
          ) : (
            <>
              {showTree &&
                filteredTree.map(({ officer, farmers }) => {
                  const isExpanded = Boolean(expandedOfficers[officer.id]) || q.length > 0;
                  const selectedInOfficer = farmers.filter((f) => selectedFarmers[f.id]).length;
                  const officerChecked = Boolean(selectedPeople[officer.id]);
                  const partial = include.farmers && selectedInOfficer > 0 && selectedInOfficer < farmers.length;
                  return (
                    <div key={officer.id} className="flex flex-col">
                      <div className="flex items-center gap-2 bg-canvas/60 px-3 py-2 hover:bg-forest-50/40">
                        <button
                          type="button"
                          onClick={() => toggleExpand(officer.id)}
                          aria-expanded={isExpanded}
                          aria-label={`Toggle farmers for ${officer.full_name}`}
                          disabled={!include.farmers}
                          className="flex h-6 w-6 items-center justify-center rounded-sm text-muted hover:bg-line/50 hover:text-ink disabled:opacity-30"
                        >
                          {isExpanded && include.farmers ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                        <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
                          <input
                            type="checkbox"
                            checked={officerChecked}
                            ref={(el) => {
                              if (el) el.indeterminate = !officerChecked && partial;
                            }}
                            onChange={() => toggleOfficer(officer.id)}
                            className="h-4 w-4 rounded-sm accent-forest-700"
                          />
                          <UserCheck className="h-4 w-4 shrink-0 text-forest-700" aria-hidden />
                          <div className="flex min-w-0 flex-1 items-center gap-2">
                            <span className="truncate text-sm font-semibold text-ink">{officer.full_name}</span>
                            <span className="mono-id shrink-0 rounded-sm border border-line bg-surface px-1.5 py-0.5 text-xs text-muted">
                              {officer.code}
                            </span>
                            {officer.field_office_name && (
                              <span className="hidden min-w-0 truncate text-xs text-muted sm:inline">· {officer.field_office_name}</span>
                            )}
                          </div>
                        </label>
                        {include.farmers && (
                          <Badge tone={selectedInOfficer > 0 ? 'success' : 'neutral'} size="sm" className="shrink-0 whitespace-nowrap">
                            {selectedInOfficer} / {farmers.length}
                          </Badge>
                        )}
                      </div>

                      {isExpanded && include.farmers && (
                        <div className="bg-surface py-2 pl-9 pr-3">
                          {farmers.length === 0 ? (
                            <p className="py-2 text-xs text-muted">No registered farmers under this field officer.</p>
                          ) : (
                            <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                              {farmers.map((farmer) => {
                                const checked = Boolean(selectedFarmers[farmer.id]);
                                return (
                                  <li key={farmer.id}>
                                    <label
                                      className={cn(
                                        'flex cursor-pointer items-center justify-between gap-2 rounded-control border px-3 py-1.5 text-sm transition-colors',
                                        checked ? 'border-forest-600 bg-forest-50/70 text-ink' : 'border-line bg-surface text-muted hover:bg-canvas',
                                      )}
                                    >
                                      <span className="flex min-w-0 items-center gap-2.5">
                                        <input
                                          type="checkbox"
                                          checked={checked}
                                          onChange={() => toggleFarmer(farmer.id)}
                                          className="h-4 w-4 shrink-0 accent-forest-700"
                                        />
                                        <Users className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
                                        <span className="truncate font-medium text-ink">{farmer.name}</span>
                                      </span>
                                      <span className="flex shrink-0 items-center gap-1.5 text-xs">
                                        <span className="mono-id text-muted">#{farmer.sawie_id}</span>
                                        <span className="rounded-sm bg-canvas px-1.5 py-0.5 text-xs text-muted tabular">
                                          {farmer.field_count} {farmer.field_count === 1 ? 'field' : 'fields'}
                                        </span>
                                      </span>
                                    </label>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}

              {include.staff && (
                <PeopleGroup title="Staff" icon={<UserCog className="h-4 w-4 text-forest-700" aria-hidden />} people={visibleStaff} selected={selectedPeople} onToggle={togglePerson} unavailable={peopleQuery.isError} />
              )}
              {include.admins && (
                <PeopleGroup title="Administrators" icon={<ShieldCheck className="h-4 w-4 text-forest-700" aria-hidden />} people={visibleAdmins} selected={selectedPeople} onToggle={togglePerson} unavailable={peopleQuery.isError} />
              )}
            </>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs text-muted">
          {format === 'csv' ? (
            <FileSpreadsheet className="h-4 w-4 text-forest-700" aria-hidden />
          ) : (
            <FileJson className="h-4 w-4 text-forest-700" aria-hidden />
          )}
          <span>One file, with a Record Type column telling farmers, officers, staff and admins apart.</span>
        </div>
      </div>
    </Dialog>
  );
}

function PeopleGroup({
  title,
  icon,
  people,
  selected,
  onToggle,
  unavailable,
}: {
  title: string;
  icon: React.ReactNode;
  people: Officer[];
  selected: Record<string, boolean>;
  onToggle: (id: string) => void;
  unavailable: boolean;
}) {
  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 bg-canvas/60 px-3 py-2 text-sm font-semibold text-ink">
        {icon}
        {title}
        <span className="text-xs font-normal text-muted">{people.length}</span>
      </div>
      {people.length === 0 ? (
        <p className="px-4 py-3 text-xs text-muted">
          {unavailable ? `Only administrators can export ${title.toLowerCase()}.` : `No ${title.toLowerCase()} found.`}
        </p>
      ) : (
        <ul>
          {people.map((p) => (
            <li key={p.id}>
              <label className="flex cursor-pointer items-center gap-3 px-4 py-1.5 text-sm hover:bg-forest-50/40">
                <input
                  type="checkbox"
                  checked={Boolean(selected[p.id])}
                  onChange={() => onToggle(p.id)}
                  className="h-4 w-4 shrink-0 accent-forest-700"
                />
                <span className="truncate font-medium text-ink">{p.full_name}</span>
                <span className="mono-id shrink-0 rounded-sm border border-line bg-surface px-1.5 py-0.5 text-xs text-muted">{p.code}</span>
                {p.field_office_name && (
                  <span className="hidden min-w-0 truncate text-xs text-muted sm:inline">· {p.field_office_name}</span>
                )}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
