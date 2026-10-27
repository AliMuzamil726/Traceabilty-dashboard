import { ArrowLeft, ArrowRight, ChevronDown, LogOut, Menu, UserRound } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useOfficerStore } from '@/core/store/officerStore';
import { useUiStore } from '@/core/store/uiStore';
import { roleLabel } from '@/core/utils/format';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { Badge } from '@/design-system/components/Badge';
import { IconButton } from '@/design-system/components/IconButton';
import { Skeleton } from '@/design-system/components/Skeleton';
import { Avatar } from '@/shared/components/Avatar';
import { showsTopbarTools } from '@/core/utils/access';
import { NotificationBell } from '@/module_1';
import { findModuleByPath } from '../moduleRegistry';
import { GlobalSearch } from './GlobalSearch';

function UserMenu() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useCurrentOfficer();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center gap-3" aria-hidden>
        <Skeleton shape="circle" className="h-9 w-9" />
        <Skeleton className="hidden w-24 xl:block" />
      </div>
    );
  }
  if (isError || !data) return <Badge tone="danger">Not signed in</Badge>;

  const queryClient = useQueryClient();
  const signOut = useOfficerStore((s) => s.signOut);

  const detail = data.field_office_name ? `${roleLabel(data.role)}, ${data.field_office_name}` : roleLabel(data.role);
  const item = 'flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-ink hover:bg-forest-50';

  const handleSignOut = () => {
    setOpen(false);
    signOut();
    queryClient.clear();
    navigate('/login', { replace: true });
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${data.full_name}, ${detail}`}
        className="flex min-w-0 items-center gap-3 rounded-pill px-2 py-1 transition-colors duration-base ease-brand hover:bg-canvas"
      >
        <Avatar officerId={data.id} name={data.full_name} hasPhoto={data.has_photo} />
        <span className="hidden min-w-0 text-left leading-tight lg:block">
          <span className="block max-w-[180px] truncate text-base font-medium text-ink">{data.full_name}</span>
          <span className="block max-w-[180px] truncate text-xs text-muted">{detail}</span>
        </span>
        <ChevronDown className="hidden h-4 w-4 text-muted lg:block" aria-hidden />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full z-40 mt-1.5 w-60 overflow-hidden rounded-card border border-line bg-surface py-1 shadow-2">
          <div className="border-b border-line px-3.5 py-2.5">
            <div className="truncate text-sm font-semibold text-ink">{data.full_name}</div>
            <div className="mt-0.5 flex items-center gap-2">
              <span className="truncate text-xs text-muted">{detail}</span>
              <Badge tone="accent" className="shrink-0">{roleLabel(data.role)}</Badge>
            </div>
          </div>
          <div className="py-1">
            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => {
                setOpen(false);
                navigate('/profile');
              }}
            >
              <UserRound className="h-4 w-4 text-muted" aria-hidden />
              My profile
            </button>
          </div>
          <div className="border-t border-line py-1">
            <button
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-danger hover:bg-danger-tint"
              onClick={handleSignOut}
            >
              <LogOut className="h-4 w-4" aria-hidden />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function Topbar() {
  const { pathname } = useLocation();
  const role = useCurrentOfficer().data?.role;
  const navigate = useNavigate();
  const setMobileNavOpen = useUiStore((s) => s.setMobileNavOpen);
  const current = findModuleByPath(pathname);
  const isKnown = Boolean(current) && (current?.path !== '/' || pathname === '/');
  const title = pathname === '/profile' ? 'My profile' : isKnown && current ? current.name : 'Page not found';
  const atStart = ((window.history.state as { idx?: number } | null)?.idx ?? 0) === 0;

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-2 border-b border-line bg-surface/95 px-3 backdrop-blur sm:gap-3 sm:px-6">
      <IconButton className="lg:hidden" label="Open navigation" icon={<Menu className="h-5 w-5" />} onClick={() => setMobileNavOpen(true)} />
      <div className="flex shrink-0 items-center gap-0.5">
        <IconButton variant="ghost" size="sm" label="Back" icon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate(-1)} disabled={atStart} />
        <IconButton variant="ghost" size="sm" label="Forward" icon={<ArrowRight className="h-4 w-4" />} onClick={() => navigate(1)} />
      </div>
      <p className="min-w-0 flex-1 truncate text-md font-semibold text-ink">{title}</p>

      {showsTopbarTools(role, pathname) && (
        <>
          <GlobalSearch className="hidden w-64 md:block xl:w-80" />
          <NotificationBell />
          <UserMenu />
        </>
      )}
    </header>
  );
}
