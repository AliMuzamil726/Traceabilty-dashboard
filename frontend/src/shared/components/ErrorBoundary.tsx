import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from '@/design-system/components/Button';

interface Props {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches render errors in one route so the shell stays usable. */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Route error', error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  override render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    const chunkFailed = /dynamically imported module|Failed to fetch|Loading chunk/i.test(error.message);
    return (
      <div role="alert" className="mx-auto flex max-w-lg flex-col items-center gap-3 px-6 py-20 text-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-card bg-danger-tint text-danger" aria-hidden>
          <AlertTriangle className="h-5 w-5" />
        </span>
        <h2 className="text-lg font-semibold text-ink">This page could not be displayed</h2>
        <p className="text-base text-muted">
          {chunkFailed
            ? 'The page files could not be loaded. Check that the frontend is still running, then reload.'
            : 'Something went wrong while showing this page. Try again, or reload the app if it keeps happening.'}
        </p>
        <p className="mono-id max-w-full truncate text-xs text-muted">{error.message}</p>
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" onClick={this.reset}>
            Try again
          </Button>
          <Button leftIcon={<RotateCcw className="h-4 w-4" />} onClick={() => window.location.reload()}>
            Reload app
          </Button>
        </div>
      </div>
    );
  }
}
