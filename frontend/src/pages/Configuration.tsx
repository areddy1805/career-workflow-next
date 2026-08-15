import { useQuery } from '@tanstack/react-query';
import { fetchSettings } from '@/lib/api';
import { Moon, Sun } from 'lucide-react';
import { usePreferences } from '@/store/preferences';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';

export default function Configuration() {
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  });

  const { theme, setTheme } = usePreferences();

  if (isLoading) {
    return <div className="p-4 max-w-4xl"><GridSkeleton rows={5} /></div>;
  }

  return (
    <div className="h-full flex flex-col bg-background p-4 sm:p-6 lg:p-8 max-w-4xl">
      <PageHeader
        coordinate="07 · 01"
        title="Configuration"
        subtitle="System settings and global preferences. Read-only view."
      />

      <div className="space-y-6">
        {/* Appearance Settings */}
        <section className="space-y-4 bg-surface border border-border/40 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            Appearance
          </h2>
          <div className="flex gap-4">
            <button
              onClick={() => setTheme('light')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md border text-sm transition-colors ${
                theme === 'light'
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-background hover:bg-secondary border-border'
              }`}
            >
              <Sun className="w-4 h-4" /> Light
            </button>
            <button
              onClick={() => setTheme('dark')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md border text-sm transition-colors ${
                theme === 'dark'
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-background hover:bg-secondary border-border'
              }`}
            >
              <Moon className="w-4 h-4" /> Dark
            </button>
          </div>
        </section>

        {/* Backend Configuration */}
        <section className="space-y-4 bg-surface border border-border/40 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            Backend Settings
          </h2>
          <div className="text-sm text-muted-foreground overflow-auto">
            <pre className="bg-secondary/20 p-4 rounded-md">
              {JSON.stringify(settings, null, 2)}
            </pre>
          </div>
        </section>
      </div>
    </div>
  );
}
