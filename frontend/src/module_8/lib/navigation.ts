import {
  Building2,
  CalendarClock,
  Database,
  Factory,
  FileSearch,
  Gauge,
  Info,
  KeyRound,
  ListTree,
  Map as MapIcon,
  QrCode,
  ShieldCheck,
  Truck,
  UserCog,
  Users,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Shown to every officer; everything else is administrator-only. */
  everyone?: boolean;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

/** The sections of Settings, grouped the way an administrator thinks about them. */
export const NAV_GROUPS: NavGroup[] = [
  {
    title: 'People and organisation',
    items: [
      { to: 'officers', label: 'Officers', icon: Users },
      { to: 'permissions', label: 'Permissions', icon: ShieldCheck },
      { to: 'offices', label: 'Field offices', icon: Building2 },
    ],
  },
  {
    title: 'Programme',
    items: [
      { to: 'crops', label: 'Crops and season', icon: CalendarClock },
      { to: 'sites', label: 'Ginners and processors', icon: Factory },
    ],
  },
  {
    title: 'Data',
    items: [
      { to: 'lists', label: 'Dropdown lists', icon: ListTree },
      { to: 'locations', label: 'Locations', icon: MapIcon },
    ],
  },
  {
    title: 'Operations',
    items: [
      { to: 'deliveries', label: 'Deliveries and heaps', icon: Truck },
      { to: 'alerts', label: 'Alerts and thresholds', icon: Gauge },
      { to: 'validation', label: 'Validation rules', icon: KeyRound },
    ],
  },
  {
    title: 'Map and QR',
    items: [
      { to: 'map', label: 'Map', icon: MapIcon },
      { to: 'qr', label: 'QR and labels', icon: QrCode },
    ],
  },
  {
    title: 'System',
    items: [
      { to: 'audit', label: 'Audit log', icon: FileSearch },
      { to: 'backup', label: 'Backup and restore', icon: Database },
      { to: 'system', label: 'System information', icon: Info },
    ],
  },
  {
    title: 'You',
    items: [
      { to: 'preferences', label: 'My preferences', icon: UserCog, everyone: true },
    ],
  },
];
