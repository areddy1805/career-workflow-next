import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { SortingState, VisibilityState } from '@tanstack/react-table';

interface JobFilters {
  status?: string;
  query?: string;
}

interface JobsState {
  sorting: SortingState;
  columnVisibility: VisibilityState;
  filters: JobFilters;
  setSorting: (updater: SortingState | ((old: SortingState) => SortingState)) => void;
  setColumnVisibility: (updater: VisibilityState | ((old: VisibilityState) => VisibilityState)) => void;
  setFilters: (filters: JobFilters) => void;
  updateFilters: (updates: Partial<JobFilters>) => void;
}

export const useJobStore = create<JobsState>()(
  persist(
    (set) => ({
      sorting: [{ id: 'last_updated_at', desc: true }],
      columnVisibility: {},
      filters: {},
      setSorting: (updater) => set((state) => ({ 
        sorting: typeof updater === 'function' ? updater(state.sorting) : updater 
      })),
      setColumnVisibility: (updater) => set((state) => ({ 
        columnVisibility: typeof updater === 'function' ? updater(state.columnVisibility) : updater 
      })),
      setFilters: (filters) => set({ filters }),
      updateFilters: (updates) => set((state) => ({ filters: { ...state.filters, ...updates } })),
    }),
    {
      name: 'cw-jobs-state',
    }
  )
);
