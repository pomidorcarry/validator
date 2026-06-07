import { describe, it, expect } from 'vitest';

describe('API_BASE', () => {
  it('should set window.API_BASE to /api/v1', async () => {
    await import('../api.js');
    expect(window.API_BASE).toBe('/api/v1');
  });
});
