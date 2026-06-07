import { describe, it, expect, vi, beforeAll } from 'vitest';

describe('themes.js', () => {
  beforeAll(async () => {
    // Import module once, tests verify behavior
    await import('../themes.js');
  });

  it('should apply original theme CSS variables on load', () => {
    const root = document.documentElement;
    expect(root.style.getPropertyValue('--bg')).toBe('#0b0914');
  });

  it('toggleTheme should switch to coffee and back', () => {
    window.toggleTheme();
    const root = document.documentElement;
    expect(root.style.getPropertyValue('--bg')).toBe('#2b2420');

    window.toggleTheme();
    expect(root.style.getPropertyValue('--bg')).toBe('#0b0914');
  });

  it('toggleTheme should update button icon', () => {
    const btn = document.getElementById('btnThemeToggle');
    window.toggleTheme();
    expect(btn.textContent).toBe('☕');
    window.toggleTheme();
    expect(btn.textContent).toBe('⬟');
  });

  it('toggleAiPopup should toggle open class on aiPopup', () => {
    const popup = document.getElementById('aiPopup');
    expect(popup.classList.contains('open')).toBe(false);
    window.toggleAiPopup();
    expect(popup.classList.contains('open')).toBe(true);
    window.toggleAiPopup();
    expect(popup.classList.contains('open')).toBe(false);
  });

  it('click outside ai-status-wrap should close popup', () => {
    window.toggleAiPopup();
    expect(document.getElementById('aiPopup').classList.contains('open')).toBe(true);

    const event = new MouseEvent('click', { bubbles: true });
    document.body.dispatchEvent(event);
    expect(document.getElementById('aiPopup').classList.contains('open')).toBe(false);
  });
});
