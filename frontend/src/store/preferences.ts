import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Density = 'compact' | 'comfortable';
type Theme = 'dark' | 'light';

interface PreferencesState {
  theme: Theme;
  density: Density;
  sidebarOpen: boolean;
  setTheme: (theme: Theme) => void;
  setDensity: (density: Density) => void;
  toggleSidebar: () => void;
}

export const usePreferences = create<PreferencesState>()(
  persist(
    (set) => ({
      theme: 'dark', // Dark by default
      density: 'compact',
      sidebarOpen: true,
      setTheme: (theme) => set({ theme }),
      setDensity: (density) => set({ density }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    }),
    {
      name: 'cw-preferences',
    }
  )
);
