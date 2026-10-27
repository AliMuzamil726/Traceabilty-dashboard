import '@fontsource-variable/inter';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import './design-system/tokens.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';

// A reload always starts fresh from the home screen (the app shell sends each role to
// its own home). The public trace page keeps its address.
const navEntry = performance.getEntriesByType?.('navigation')[0] as PerformanceNavigationTiming | undefined;
if (navEntry?.type === 'reload' && !window.location.pathname.startsWith('/trace/') && window.location.pathname !== '/login') {
  window.history.replaceState(null, '', '/');
}

const root = document.getElementById('root');
if (!root) throw new Error('Root element #root not found');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
