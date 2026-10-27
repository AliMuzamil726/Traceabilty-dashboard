import { motion } from 'framer-motion';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { useUiStore } from '@/core/store/uiStore';
import { canOpen } from '@/core/utils/access';
import { cn } from '@/core/utils/cn';
import { StatusPillOnDark } from '@/design-system/components/Badge';
import { Tooltip } from '@/design-system/components/Tooltip';
import { transition } from '@/design-system/motion';
import { MODULES, statusLabel, type ModuleEntry } from '../moduleRegistry';
import { BrandMark } from './BrandMark';

const ITEM =
  'group relative flex h-12 items-center gap-3.5 whitespace-nowrap rounded-control px-3.5 text-base font-medium transition-all duration-slow ease-brand';

function NavPill({ entry }: { entry: ModuleEntry }) {
  const label = statusLabel(entry);
  if (!label) return null;
  return <StatusPillOnDark tone={label === 'In build' ? 'accent' : 'neutral'}>{label}</StatusPillOnDark>;
}

function NavItem({ entry, collapsed, onNavigate }: { entry: ModuleEntry; collapsed: boolean; onNavigate?: () => void }) {
  const Icon = entry.icon;
  const link = (
    <NavLink
      to={entry.path}
      end={entry.path === '/'}
      onClick={onNavigate}
      aria-label={collapsed ? entry.name : undefined}
      className={({ isActive }) =>
        cn(
          ITEM,
          isActive
            ? 'bg-forest-800/90 text-white shadow-1 ring-1 ring-white/10 backdrop-blur-sm'
            : 'text-forest-100/80 hover:bg-white/8 hover:text-white hover:shadow-1',
          collapsed && 'justify-center px-0',
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="sidebar-active"
              className="absolute -left-2.5 top-2.5 bottom-2.5 w-[3.5px] rounded-r-pill bg-wheat-500"
              transition={transition('base')}
              aria-hidden
            />
          )}
          <Icon className={cn('h-5 w-5 shrink-0 transition-all duration-base group-hover:scale-[1.08]', isActive ? 'text-wheat-300 drop-shadow-[0_0_6px_rgba(255,200,100,0.25)]' : 'text-forest-100/70 group-hover:text-forest-100')} aria-hidden />
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1 truncate">{entry.name}</span>
              <NavPill entry={entry} />
            </>
          )}
        </>
      )}
    </NavLink>
  );
  return collapsed ? (
    <Tooltip content={entry.name} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

function DisabledItem({ entry, collapsed }: { entry: ModuleEntry; collapsed: boolean }) {
  const Icon = entry.icon;
  const item = (
    <span
      role="link"
      aria-disabled="true"
      aria-label={`${entry.name} (coming later)`}
      tabIndex={collapsed ? 0 : -1}
      className={cn(ITEM, 'cursor-not-allowed text-forest-100/45', collapsed && 'justify-center px-0')}
    >
      <Icon className="h-5 w-5 shrink-0" aria-hidden />
      {!collapsed && (
        <>
          <span className="flex-1">{entry.name}</span>
          <NavPill entry={entry} />
        </>
      )}
    </span>
  );
  return collapsed ? (
    <Tooltip content={`${entry.name}: coming later`} side="right">
      {item}
    </Tooltip>
  ) : (
    item
  );
}

export interface SidebarContentProps {
  collapsed?: boolean;
  /** Called after a navigation (closes the mobile drawer). */
  onNavigate?: () => void;
  /** Show the collapse toggle (desktop rail only). */
  showCollapseToggle?: boolean;
}

/**
 * Brand block plus the eight module items.
 *
 * Narrower desktop rail (228px expanded, 68px collapsed) with larger item sizing and
 * balanced vertical distribution so navigation items comfortably fill the sidebar height.
 */
export function SidebarContent({ collapsed = false, onNavigate, showCollapseToggle = false }: SidebarContentProps) {
  const toggle = useUiStore((s) => s.toggleSidebar);
  const me = useCurrentOfficer().data;
  const role = me?.role;
  const action = cn(ITEM, 'h-11 w-full text-forest-100/85 hover:bg-white/10 hover:text-white');

  const visible = MODULES.filter((m) => canOpen(role, m.path));
  const main = visible.filter((m) => m.path !== '/settings' && m.status !== 'deferred');
  const pinned = visible.filter((m) => m.path === '/settings' || m.status === 'deferred');

  return (
    <div className="flex h-full flex-col border-r border-white/10 bg-gradient-to-b from-forest-900 via-forest-900 to-forest-950 text-white select-none">
      <div className={cn('flex h-16 shrink-0 items-center gap-3 overflow-hidden whitespace-nowrap border-b border-white/[0.08] px-4', collapsed && 'justify-center px-0')}>
        <span className="shrink-0">
          <BrandMark />
        </span>
        {!collapsed && (
          <div className="min-w-0 flex-1 leading-tight">
            <div className="text-md font-semibold tracking-[0.02em]">SAWiE</div>
            <div className="truncate text-xs text-forest-100/75">Fibre Traceability</div>
          </div>
        )}
      </div>

      <nav aria-label="Primary" className="flex min-h-0 flex-1 flex-col justify-between overflow-y-auto overflow-x-hidden px-2.5 py-4">
        <ul className="flex flex-1 flex-col justify-evenly gap-2 py-1">
          {main.map((m) => (
            <li key={m.number}>
              <NavItem entry={m} collapsed={collapsed} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
        <ul className={cn('mt-4 flex flex-col gap-1.5 pt-3', pinned.length > 0 && 'border-t border-white/10')}>
          {pinned.map((m) => (
            <li key={m.number}>
              {m.status === 'deferred' ? (
                <DisabledItem entry={m} collapsed={collapsed} />
              ) : (
                <NavItem entry={m} collapsed={collapsed} onNavigate={onNavigate} />
              )}
            </li>
          ))}
          {showCollapseToggle && (
            <li>
              {collapsed ? (
                <Tooltip content="Expand sidebar" side="right">
                  <button type="button" onClick={toggle} aria-label="Expand sidebar" className={cn(action, 'justify-center px-0')}>
                    <PanelLeftOpen className="h-5 w-5 shrink-0" aria-hidden />
                  </button>
                </Tooltip>
              ) : (
                <button type="button" onClick={toggle} aria-label="Collapse sidebar" className={action}>
                  <PanelLeftClose className="h-5 w-5 shrink-0" aria-hidden />
                  <span className="flex-1 text-left">Collapse</span>
                </button>
              )}
            </li>
          )}
        </ul>
      </nav>
    </div>
  );
}

/** Desktop sidebar: 228px, collapsible to a 68px icon rail (width animates smoothly). */
export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 68 : 228 }}
      transition={transition('slow')}
      className="sticky top-0 hidden h-screen shrink-0 overflow-hidden shadow-1 lg:block"
      aria-label="Sidebar"
    >
      <SidebarContent collapsed={collapsed} showCollapseToggle />
    </motion.aside>
  );
}
