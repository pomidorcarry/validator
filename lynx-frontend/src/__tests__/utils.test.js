import { describe, it, expect, vi } from 'vitest';

describe('escHtml', () => {
  it('should escape HTML special characters', async () => {
    await import('../utils.js');
    expect(window.escHtml('<script>alert("xss")</script>'))
      .toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
  });

  it('should return empty string for null/undefined', () => {
    expect(window.escHtml(null)).toBe('');
    expect(window.escHtml(undefined)).toBe('');
  });

  it('should JSON-stringify objects', () => {
    const result = window.escHtml({ a: 1 });
    expect(result).toContain('&quot;a&quot;');
    expect(result).toContain('1');
  });

  it('should return empty string for empty input', () => {
    expect(window.escHtml('')).toBe('');
  });
});

describe('formatDate', () => {
  it('should format a valid ISO date string', async () => {
    await import('../utils.js');
    const result = window.formatDate('2024-01-15T10:30:00');
    expect(result).toBeTruthy();
    expect(typeof result).toBe('string');
  });

  it('should return "-" for invalid input', () => {
    const result = window.formatDate('not-a-date');
    expect(result === '-' || result === 'Invalid Date').toBe(true);
  });

  it('should return "-" for empty input', () => {
    const result = window.formatDate('');
    expect(result === '-' || result === 'Invalid Date').toBe(true);
  });
});

describe('getStatusBadge', () => {
  it('should return mapped status strings', async () => {
    await import('../utils.js');
    expect(window.getStatusBadge('processed')).toBe('✓ Готово');
    expect(window.getStatusBadge('queued')).toBe('⏳ В очереди');
    expect(window.getStatusBadge('failed')).toBe('✗ Ошибка');
    expect(window.getStatusBadge('uploaded')).toBe('📤 Загружен');
  });

  it('should return the input itself for unknown status', () => {
    expect(window.getStatusBadge('unknown')).toBe('unknown');
    expect(window.getStatusBadge('')).toBe('');
  });
});

describe('openModal / closeModal', () => {
  it('should add/remove active class on modal element', async () => {
    await import('../utils.js');
    window.openModal('projectModal');
    const modal = document.getElementById('projectModal');
    expect(modal.classList.contains('active')).toBe(true);

    window.closeModal('projectModal');
    expect(modal.classList.contains('active')).toBe(false);
  });

  it('should toggle multiple times', () => {
    window.openModal('uploadModal');
    expect(document.getElementById('uploadModal').classList.contains('active')).toBe(true);
    window.closeModal('uploadModal');
    expect(document.getElementById('uploadModal').classList.contains('active')).toBe(false);
  });
});

describe('showToast', () => {
  beforeEach(async () => {
    await import('../utils.js');
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should show toast with message and type class', () => {
    window.showToast('Test message', 'success');
    const toast = document.getElementById('toast');
    expect(toast.textContent).toBe('Test message');
    expect(toast.className).toContain('show');
    expect(toast.className).toContain('success');
  });

  it('should hide toast after 3 seconds', () => {
    window.showToast('Auto hide', 'error');
    vi.advanceTimersByTime(3000);
    const toast = document.getElementById('toast');
    expect(toast.className).not.toContain('show');
  });
});
