import { useQuery } from '@tanstack/react-query';
import { fetchSettings } from '@/lib/api';
import { Settings2, SlidersHorizontal, Monitor, Moon, Sun } from 'lucide-react';
import { usePreferences } from '@/store/preferences';

export default function Settings() {
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  });

  const { theme, setTheme } = usePreferences();

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      {/* Page Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/40 shrink-0 bg-background z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Settings</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage your interface preferences and view active environment configuration.
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 lg:p-10">
        <div className="max-w-3xl space-y-12">
          
          {/* Frontend Preferences */}
          <section className="space-y-4">
            <div>
              <h3 className="font-semibold text-sm text-foreground">Interface Preferences</h3>
              <p className="text-xs text-muted-foreground mt-1">Customize how the application looks and feels.</p>
            </div>
            
            <div className="border border-border/40 rounded-lg p-5 bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="font-medium text-sm">Theme</p>
                <p className="text-xs text-muted-foreground mt-0.5">Select your color scheme preference.</p>
              </div>
              <div className="flex bg-muted/50 rounded-md p-1 border border-border/40 shrink-0">
                <button 
                  onClick={() => setTheme('light')}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-medium transition-colors ${theme === 'light' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  <Sun className="w-3.5 h-3.5" /> Light
                </button>
                <button 
                  onClick={() => setTheme('dark')}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-medium transition-colors ${theme === 'dark' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  <Moon className="w-3.5 h-3.5" /> Dark
                </button>
              </div>
            </div>
          </section>

          {/* Backend Environment */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-sm text-foreground">Environment Configuration</h3>
                <p className="text-xs text-muted-foreground mt-1">Active backend variables and feature flags.</p>
              </div>
              <span className="text-[9px] uppercase font-mono bg-muted px-2 py-1 rounded text-muted-foreground tracking-wider font-semibold">Read-Only</span>
            </div>

            <div className="border border-border/40 rounded-lg overflow-hidden bg-card">
              {isLoading ? (
                <div className="p-4 space-y-3">
                  {[1, 2, 3, 4].map(i => <div key={i} className="h-6 w-full bg-muted animate-pulse rounded" />)}
                </div>
              ) : (
                <div className="divide-y divide-border/40">
                  {Object.entries(settings || {}).map(([key, value]) => (
                    <div key={key} className="flex flex-col sm:flex-row sm:items-center justify-between p-3 px-4 hover:bg-muted/30 transition-colors gap-2">
                      <p className="text-[11px] font-mono text-muted-foreground shrink-0">{key}</p>
                      <p className="font-mono text-xs text-foreground truncate text-right">
                        {value != null && value !== '' ? String(value) : <span className="text-muted-foreground/40 italic">Not Set</span>}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
