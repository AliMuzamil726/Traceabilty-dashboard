import { motion } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Home, LogOut, NotebookPen, UserRound, Users } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { useOfficerStore } from '@/core/store/officerStore';
import { cn } from '@/core/utils/cn';
import { roleLabel } from '@/core/utils/format';
import { Avatar } from '@/shared/components/Avatar';
import { transition } from '@/design-system/motion';
import { BrandMark } from './BrandMark';

interface Tab {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const TABS: Tab[] = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/register', label: 'Farmers', icon: Users, end: true },
  { to: '/fieldbook', label: 'Fieldbook', icon: NotebookPen },
];

/**
 * The field officer's frame. Includes top bar with quick profile/sign-out controls
 * and bottom navigation bar with Home, Farmers, Add Field, Fieldbook, and Profile.
 */
export function OfficerShell({ children }: { children: ReactNode }) {
  const me = useCurrentOfficer().data;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const signOut = useOfficerStore((s) => s.signOut);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  const handleSignOut = () => {
    setMenuOpen(false);
    signOut();
    queryClient.clear();
    navigate('/login', { replace: true });
  };

  const detail = me?.field_office_name
    ? `${roleLabel(me.role)}, ${me.field_office_name}`
    : me
      ? roleLabel(me.role)
      : 'Field officer';

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur">
        <BrandMark size={28} />
        <span className="min-w-0 flex-1 truncate text-md font-semibold text-ink">SAWiE</span>

        <div className="flex items-center gap-2">
          <div ref={menuRef} className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Account menu"
              className="flex items-center gap-2 rounded-pill border border-line bg-canvas px-2 py-1 hover:bg-forest-50"
            >
              <Avatar officerId={me?.id} name={me?.full_name} hasPhoto={me?.has_photo} />
              <span className="hidden max-w-[140px] truncate text-sm font-medium text-ink md:block">
                {me?.full_name ?? 'Account'}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-muted" aria-hidden />
            </button>

            {menuOpen && (
              <div
                role="menu"
                className="absolute right-0 top-full z-50 mt-1.5 w-56 overflow-hidden rounded-card border border-line bg-surface py-1 shadow-2"
              >
                {me && (
                  <div className="border-b border-line px-3.5 py-2.5">
                    <div className="truncate text-sm font-semibold text-ink">{me.full_name}</div>
                    <div className="truncate text-xs text-muted">{detail}</div>
                  </div>
                )}
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    navigate('/profile');
                  }}
                  className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-ink hover:bg-forest-50"
                >
                  <UserRound className="h-4 w-4 text-muted" aria-hidden />
                  My profile
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={handleSignOut}
                  className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-danger hover:bg-danger-tint"
                >
                  <LogOut className="h-4 w-4" aria-hidden />
                  {me ? `Sign out, ${me.full_name.split(' ')[0]}` : 'Sign out'}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main id="main" className="min-w-0 flex-1 pb-[88px]" tabIndex={-1}>
        {children}
      </main>

      <nav
        aria-label="Primary"
        className="fixed bottom-0 left-0 right-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
      >
        <ul className="mx-auto flex max-w-2xl">
          {TABS.map((tab) => (
            <li key={tab.to} className="flex-1">
              <NavLink
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  cn(
                    'relative flex h-[68px] flex-col items-center justify-center gap-1 text-xs font-medium transition-colors duration-base ease-brand',
                    isActive ? 'text-forest-800 font-semibold' : 'text-muted hover:text-ink',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.span
                        layoutId="officer-nav-pill"
                        className="absolute top-1.5 h-[3px] w-10 rounded-pill bg-forest-700"
                        transition={transition('base')}
                        aria-hidden
                      />
                    )}
                    <tab.icon className={cn('h-5 w-5 sm:h-6 sm:w-6 transition-transform duration-base', isActive && 'text-forest-700 scale-110')} aria-hidden />
                    {tab.label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
