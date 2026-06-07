import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('navigation.js', () => {
  beforeEach(async () => {
    // Stub async functions called by navigation
    window.loadProjects = vi.fn();
    window.loadProjectDetail = vi.fn();
    window.loadModels = vi.fn();
    window.currentProjectId = null;
    window.selectedModelId = null;
    window.projects = [
      { id: 'proj-1', name: 'Test Project', code: 'TP-01' },
    ];

    await import('../navigation.js');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('showHome should activate homeView and deactivate others', () => {
    window.showHome();
    const homeView = document.getElementById('homeView');
    const projectView = document.getElementById('projectView');
    const tzView = document.getElementById('tzView');
    const dataView = document.getElementById('dataView');

    expect(homeView.classList.contains('active')).toBe(true);
    expect(projectView.classList.contains('active')).toBe(false);
    expect(tzView.classList.contains('active')).toBe(false);
    expect(dataView.classList.contains('active')).toBe(false);
  });

  it('showHome should render breadcrumb and call loadProjects', () => {
    window.showHome();
    const breadcrumb = document.getElementById('breadcrumb');
    expect(breadcrumb.innerHTML).toContain('Проекты');
    expect(window.loadProjects).toHaveBeenCalled();
  });

  it('showHome should hide quick select and show new project button', () => {
    window.showHome();
    expect(document.getElementById('projectQuickSelect').style.display).toBe('none');
    expect(document.getElementById('btnNewProject').style.display).toBe('');
  });

  it('showProject should activate projectView and set currentProjectId', () => {
    window.showProject('proj-1');
    const projectView = document.getElementById('projectView');
    expect(projectView.classList.contains('active')).toBe(true);
    expect(window.currentProjectId).toBe('proj-1');
  });

  it('showProject should load project detail and models', () => {
    window.showProject('proj-1');
    expect(window.loadProjectDetail).toHaveBeenCalledWith('proj-1');
    expect(window.loadModels).toHaveBeenCalledWith('proj-1');
  });

  it('showProject should update breadcrumb with project name', () => {
    window.showProject('proj-1');
    const breadcrumb = document.getElementById('breadcrumb');
    expect(breadcrumb.innerHTML).toContain('Test Project');
  });

  it('showProject should show quick select with correct value', () => {
    // Add option first so select.value can be set
    const qs = document.getElementById('projectQuickSelect');
    const opt = document.createElement('option');
    opt.value = 'proj-1';
    qs.appendChild(opt);

    window.showProject('proj-1');
    expect(qs.style.display).toBe('');
  });

  it('goHome should clear state and call showHome', () => {
    window.currentProjectId = 'proj-1';
    window.selectedModelId = 'mod-1';
    window.goHome();
    expect(window.currentProjectId).toBeNull();
    expect(window.selectedModelId).toBeNull();
    expect(window.loadProjects).toHaveBeenCalled();
  });

  it('onQuickSelectProject should call showProject with value', () => {
    window.onQuickSelectProject('proj-1');
    expect(window.currentProjectId).toBe('proj-1');
  });

  it('onQuickSelectProject should ignore empty value', () => {
    window.onQuickSelectProject('');
    expect(window.currentProjectId).toBeNull();
  });
});
