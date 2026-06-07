import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('categories.js', () => {
  beforeEach(async () => {
    window.CATEGORIES = [];
    window.CATEGORY_ICONS = {};
    window.__CATEGORY_COLUMNS = [];
    window.currentProjectId = null;
    await import('../categories.js');
  });

  describe('buildCategoryIcons', () => {
    it('should return icon map with colors for each category', () => {
      const icons = window.buildCategoryIcons(['Pipes', 'Fittings', 'Valves']);
      expect(Object.keys(icons)).toEqual(['Pipes', 'Fittings', 'Valves']);
      expect(icons.Pipes.color).toMatch(/^#[0-9a-f]{6}$/);
      expect(icons.Pipes.icon).toBe('');
    });

    it('should cycle colors for more categories than colors available', () => {
      const names = Array.from({ length: 12 }, (_, i) => `Cat${i}`);
      const icons = window.buildCategoryIcons(names);
      // First and 11th should have different colors due to cycling
      expect(icons.Cat0.color).toBe(icons.Cat10.color);
    });

    it('should return empty object for empty list', () => {
      expect(window.buildCategoryIcons([])).toEqual({});
    });
  });

  describe('getDefaultCols', () => {
    it('should return columns for known category', () => {
      const cols = window.getDefaultCols('Труба металлическая');
      expect(cols.length).toBeGreaterThan(0);
      expect(cols[0].label).toBe('Секция');
    });

    it('should return empty array for unknown category', () => {
      expect(window.getDefaultCols('Unknown')).toEqual([]);
    });
  });

  describe('getColsForCategory', () => {
    it('should return saved columns if they exist', () => {
      window.__CATEGORY_COLUMNS = [
        { cat: 'Pipes', cols: [{ label: 'Size' }] },
      ];
      const cols = window.getColsForCategory('Pipes');
      expect(cols).toEqual([{ label: 'Size' }]);
    });

    it('should return empty array for unknown category', () => {
      window.__CATEGORY_COLUMNS = [];
      expect(window.getColsForCategory('Nope')).toEqual([]);
    });
  });

  describe('extractProp', () => {
    const rawPsets = {
      'PSet_PipeSegmentCommon': {
        'Diameter': '50',
        'Length': '3000',
      },
      'MyParams': {
        'ADSK_Номер секции': '1',
      },
    };

    it('should find a property by single key', () => {
      const val = window.extractProp(rawPsets, ['Diameter']);
      expect(val).toBe('50');
    });

    it('should find a property by fallback keys', () => {
      const val = window.extractProp(rawPsets, ['DN', 'NominalDiameter', 'Diameter']);
      expect(val).toBe('50');
    });

    it('should return null for missing property', () => {
      const val = window.extractProp(rawPsets, ['NonExistent']);
      expect(val).toBeNull();
    });

    it('should return null for null input', () => {
      expect(window.extractProp(null, ['key'])).toBeNull();
    });

    it('should return null for non-object input', () => {
      expect(window.extractProp('string', ['key'])).toBeNull();
    });

    it('should skip empty string values', () => {
      const psets = { 'PSet': { 'Key': '' } };
      expect(window.extractProp(psets, ['Key'])).toBeNull();
    });
  });

  describe('formatValue', () => {
    it('should format number as 2 decimal places', () => {
      expect(window.formatValue(50)).toBe('50.00');
      expect(window.formatValue(3.14159)).toBe('3.14');
      expect(window.formatValue('10.5')).toBe('10.50');
    });

    it('should handle comma as decimal separator', () => {
      expect(window.formatValue('10,5')).toBe('10.50');
    });

    it('should return string as-is for non-numeric values', () => {
      expect(window.formatValue('hello')).toBe('hello');
    });

    it('should return null for null/undefined/empty', () => {
      expect(window.formatValue(null)).toBeNull();
      expect(window.formatValue(undefined)).toBeNull();
      expect(window.formatValue('   ')).toBeNull();
    });
  });

  describe('categorizeElement', () => {
    it('should return matching category by model_group substring', () => {
      window.CATEGORIES = ['Труба металлическая', 'Арматура труб'];
      const el = { model_group: 'Труба металлическая DN50' };
      expect(window.categorizeElement(el)).toBe('Труба металлическая');
    });

    it('should return fallback category when no match found', () => {
      window.CATEGORIES = ['Pipes', 'Fittings'];
      const el = { model_group: 'Unknown' };
      expect(window.categorizeElement(el)).toBe('Невалидируемое семейство');
    });

    it('should be case-insensitive', () => {
      window.CATEGORIES = ['Труба металлическая'];
      const el = { model_group: 'труба МЕТАЛЛИЧЕСКАЯ DN50' };
      expect(window.categorizeElement(el)).toBe('Труба металлическая');
    });

    it('should handle empty model_group', () => {
      window.CATEGORIES = ['Pipes'];
      const el = { model_group: '' };
      expect(window.categorizeElement(el)).toBe('Невалидируемое семейство');
    });
  });
});
