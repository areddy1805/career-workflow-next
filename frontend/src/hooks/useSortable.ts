import { useCallback, useState } from 'react';
import { applySort, cycleSort, SortState, SortType } from '@/lib/sort';

/**
 * Hook for managing sortable table state.
 *
 * @param typeMap Column → sort type mapping
 * @returns sort state and utilities to use in a table component
 */
export function useSortable(typeMap: Record<string, SortType> = {}) {
  const [sort, setSort] = useState<SortState>({ column: '', direction: null });

  const handleSort = useCallback((column: string) => {
    setSort(prev => cycleSort(prev, column));
  }, []);

  const resetSort = useCallback(() => {
    setSort({ column: '', direction: null });
  }, []);

  return {
    sort,
    handleSort,
    resetSort,
    setSort,
    typeMap,
  };
}

/**
 * Apply sorting to data.
 * Re-exported for convenience so pages don't need both imports.
 */
export function sortData<T>(
  data: T[],
  sort: SortState,
  typeMap: Record<string, SortType>,
): T[] {
  return applySort(data, sort, typeMap);
}
