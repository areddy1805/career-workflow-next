/// <reference types="vitest" />
import { describe, it, expect } from 'vitest';
import { applySort, cycleSort, SortState, SortType } from '@/lib/sort';

const TYPE_MAP: Record<string, SortType> = {
  name: 'text',
  age: 'number',
  score: 'score',
  joined: 'date',
  status: 'status',
};

const DATA = [
  { name: 'Charlie', age: 30, score: 85, joined: '2024-01-15', status: 'ACTIVE' },
  { name: 'Alice',   age: 25, score: 92, joined: '2023-06-01', status: 'PENDING' },
  { name: 'Bob',     age: 35, score: null, joined: '2024-08-20', status: 'REJECTED' },
  { name: 'Diana',   age: null, score: 78, joined: null, status: 'ACTIVE' },
  { name: 'alice',   age: 25, score: 92, joined: '2023-06-01', status: 'PENDING' },
];

describe('cycleSort', () => {
  it('starts with asc on first click', () => {
    expect(cycleSort({ column: '', direction: null }, 'name'))
      .toEqual({ column: 'name', direction: 'asc' });
  });

  it('cycles to desc on second click', () => {
    const s: SortState = { column: 'name', direction: 'asc' };
    expect(cycleSort(s, 'name'))
      .toEqual({ column: 'name', direction: 'desc' });
  });

  it('cycles to null on third click', () => {
    const s: SortState = { column: 'name', direction: 'desc' };
    expect(cycleSort(s, 'name'))
      .toEqual({ column: '', direction: null });
  });

  it('switches to asc when clicking a different column', () => {
    const s: SortState = { column: 'age', direction: 'desc' };
    expect(cycleSort(s, 'name'))
      .toEqual({ column: 'name', direction: 'asc' });
  });
});

describe('applySort', () => {
  it('returns a copy when no sort is active', () => {
    const s: SortState = { column: '', direction: null };
    const result = applySort(DATA, s, TYPE_MAP);
    expect(result).toEqual(DATA);
    expect(result).not.toBe(DATA); // different reference
  });

  it('sorts text ascending (case-insensitive)', () => {
    const s: SortState = { column: 'name', direction: 'asc' };
    const result = applySort(DATA, s, TYPE_MAP);
    const names = result.map(r => r.name);
    expect(names).toEqual(['Alice', 'alice', 'Bob', 'Charlie', 'Diana']);
  });

  it('sorts text descending', () => {
    const s: SortState = { column: 'name', direction: 'desc' };
    const result = applySort(DATA, s, TYPE_MAP);
    const names = result.map(r => r.name);
    expect(names).toEqual(['Diana', 'Charlie', 'Bob', 'Alice', 'alice']);
  });

  it('sorts numbers ascending', () => {
    const s: SortState = { column: 'age', direction: 'asc' };
    const result = applySort(DATA, s, TYPE_MAP);
    const ages = result.map(r => r.age);
    // null sorts to bottom
    expect(ages).toEqual([25, 25, 30, 35, null]);
  });

  it('sorts scores descending', () => {
    const s: SortState = { column: 'score', direction: 'desc' };
    const result = applySort(DATA, s, TYPE_MAP);
    const scores = result.map(r => r.score);
    expect(scores).toEqual([92, 92, 85, 78, null]);
  });

  it('sorts dates ascending', () => {
    const s: SortState = { column: 'joined', direction: 'asc' };
    const result = applySort(DATA, s, TYPE_MAP);
    const dates = result.map(r => r.joined);
    expect(dates).toEqual(['2023-06-01', '2023-06-01', '2024-01-15', '2024-08-20', null]);
  });

  it('is stable: equal values preserve original order', () => {
    const s: SortState = { column: 'age', direction: 'asc' };
    const result = applySort(DATA, s, TYPE_MAP);
    // Alice (index 1) and alice (index 4) have the same age
    const aliceIdx = result.findIndex(r => r.name === 'Alice');
    const aliceLowerIdx = result.findIndex(r => r.name === 'alice');
    expect(aliceIdx).toBeLessThan(aliceLowerIdx);
  });

  it('handles empty data', () => {
    const s: SortState = { column: 'name', direction: 'asc' };
    expect(applySort([], s, TYPE_MAP)).toEqual([]);
  });

  it('handles unknown column gracefully', () => {
    const s: SortState = { column: 'nonexistent', direction: 'asc' };
    const result = applySort(DATA, s, TYPE_MAP);
    expect(result).toHaveLength(DATA.length);
  });

  it('sorts status enum', () => {
    const s: SortState = { column: 'status', direction: 'asc' };
    const result = applySort(DATA, s, TYPE_MAP);
    expect(result[0].status).toBe('ACTIVE');
  });
});
