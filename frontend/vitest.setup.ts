import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Unmount React trees and clear localStorage between tests.
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});
