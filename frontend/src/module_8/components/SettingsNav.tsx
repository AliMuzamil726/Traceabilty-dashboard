import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { NAV_GROUPS } from '../lib/navigation';
import { cn } from '@/core/utils/cn';
import { Select } from '@/design-system/components/Select';

const ALL_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

export function SettingsNav() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const current = ALL_ITEMS.find((item) => pathname.endsWith(`/${item.to}`))?.to ?? 'officers';

  return (
    <>
      {/* A phone has no room for a second column, so the sections become one select. */}
      <div className="lg:hidden">
        <label htmlFor="settings-section" className="mb-1 block text-sm font-medium text-muted">
          Section
        </label>
        <Select
          id="settings-section"
          value={current}
          onChange={(event) => navigate(`/settings/${event.target.value}`)}
          options={NAV_GROUPS.flatMap((group) =>
            group.items.map((item) => ({
              value: item.to,
              label: `${group.title}: ${item.label}`,
            })),
          )}
        />
      </div>

      <nav aria-label="Settings sections" className="hidden lg:block">
        <ul className="flex flex-col gap-5">
          {NAV_GROUPS.map((group) => (
            <li key={group.title}>
              <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wide text-muted">
                {group.title}
              </p>
              <ul className="flex flex-col gap-0.5">
                {group.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={`/settings/${item.to}`}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-2.5 rounded-control px-3 py-2 text-sm transition-colors duration-base ease-brand',
                          isActive
                            ? 'bg-forest-50 font-medium text-forest-800'
                            : 'text-ink hover:bg-canvas',
                        )
                      }
                    >
                      <item.icon className="h-4 w-4 shrink-0 text-muted" aria-hidden />
                      <span className="min-w-0 truncate">{item.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}
