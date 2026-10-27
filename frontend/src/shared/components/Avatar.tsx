import { useState } from 'react';
import { API_BASE_URL } from '@/core/api/client';
import { cn } from '@/core/utils/cn';
import { initials } from '@/core/utils/format';

export interface AvatarProps {
  officerId: string | null | undefined;
  name: string | null | undefined;
  /** False (or a photo that will not load) falls back to the person's initials. */
  hasPhoto?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZES = {
  sm: 'h-9 w-9 text-sm',
  md: 'h-12 w-12 text-base',
  lg: 'h-16 w-16 text-lg',
} as const;

function photoUrl(officerId: string): string {
  return `${API_BASE_URL}/v1/officers/${officerId}/photo`;
}

/** A person's profile photo, or their initials until there is one. */
export function Avatar({ officerId, name, hasPhoto = false, size = 'sm', className }: AvatarProps) {
  const [failed, setFailed] = useState(false);
  const shows = hasPhoto && officerId && !failed;
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-wheat-100 font-semibold text-forest-900',
        SIZES[size],
        className,
      )}
      aria-hidden
    >
      {shows ? (
        <img src={photoUrl(officerId)} alt="" className="h-full w-full object-cover" onError={() => setFailed(true)} />
      ) : (
        initials(name)
      )}
    </span>
  );
}
