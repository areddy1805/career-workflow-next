/**
 * Generic sort utilities for table columns.
 *
 * Supports three-click cycle: asc → desc → none
 * Stable sort: equal values preserve their original order.
 * Null/empty values always sort to the bottom.
 */

export type SortDirection = 'asc' | 'desc' | null;

export interface SortState {
  column: string;
  direction: SortDirection;
}

export type SortType = 'text' | 'number' | 'date' | 'status' | 'score';

/**
 * Parsed sort configuration for a column.
 */
export interface SortConfig {
  key: string;
  type?: SortType;
  label: string;
}

/**
 * Cycle the sort: null → asc → desc → null → ...
 */
export function cycleSort(
  current: SortState,
  clickedColumn: string,
): SortState {
  if (current.column !== clickedColumn) {
    return { column: clickedColumn, direction: 'asc' };
  }
  if (current.direction === 'asc') {
    return { column: clickedColumn, direction: 'desc' };
  }
  return { column: '', direction: null };
}

/**
 * Extract a comparable value from a row for sorting.
 * Returns [defined, value] where defined=false means null/empty.
 */
function extractValue(row: any, key: string, type: SortType): [boolean, any] {
  const raw = key.split('.').reduce((o: any, k: string) => (o ?? {})[k], row);
  if (raw === null || raw === undefined || raw === '') {
    return [false, null];
  }

  switch (type) {
    case 'number':
    case 'score':
      return [true, Number(raw)];
    case 'date':
      return [true, new Date(raw).getTime()];
    case 'text':
    case 'status':
    default:
      return [true, String(raw).toLowerCase()];
  }
}

/**
 * Stable sort comparator factory.
 * Uses original index as tiebreaker for stability.
 */
function compare(
  a: [any, number, boolean],
  b: [any, number, boolean],
  direction: 'asc' | 'desc',
): number {
  const [aVal, aIdx, aDefined] = a;
  const [bVal, bIdx, bDefined] = b;

  // Null/empty always go to bottom
  if (!aDefined && !bDefined) return aIdx - bIdx;
  if (!aDefined) return 1;
  if (!bDefined) return -1;

  // Compare by value
  let cmp = 0;
  if (typeof aVal === 'string' && typeof bVal === 'string') {
    cmp = aVal.localeCompare(bVal);
  } else if (typeof aVal === 'number' && typeof bVal === 'number') {
    cmp = aVal - bVal;
  } else {
    cmp = String(aVal).localeCompare(String(bVal));
  }

  if (direction === 'desc') cmp = -cmp;
  return cmp === 0 ? aIdx - bIdx : cmp;
}

/**
 * Sort data in place using the given sort state.
 * Returns a new sorted array (immutable).
 */
export function applySort<T>(
  data: T[],
  sort: SortState,
  typeMap: Record<string, SortType>,
): T[] {
  if (!sort.direction || !sort.column) {
    return [...data];
  }

  const type = typeMap[sort.column] ?? 'text';

  const indexed = data.map((row, idx) => {
    const [defined, value] = extractValue(row, sort.column, type);
    return [value, idx, defined] as [any, number, boolean];
  });

  indexed.sort((a, b) => compare(a, b, sort.direction!));

  return indexed.map(([, idx]) => data[idx]);
}

/**
 * Direction arrow indicator.
 */
export function sortIndicator(direction: SortDirection): string {
  if (direction === 'asc') return ' ↑';
  if (direction === 'desc') return ' ↓';
  return '';
}
