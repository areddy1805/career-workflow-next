import { TableHead } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { SortState, sortIndicator } from '@/lib/sort';
import { ArrowUpDown } from 'lucide-react';

interface SortableHeaderProps {
  column: string;
  label: string;
  sort: SortState;
  onSort: (column: string) => void;
  className?: string;
  align?: 'left' | 'right' | 'center';
}

/**
 * A clickable table column header that supports three-click sorting:
 *   click 1: asc ↑
 *   click 2: desc ↓
 *   click 3: none (neutral)
 */
export function SortableHeader({
  column,
  label,
  sort,
  onSort,
  className,
  align = 'left',
}: SortableHeaderProps) {
  const isActive = sort.column === column;
  const indicator = isActive ? sortIndicator(sort.direction) : '';
  const ariaSort = isActive
    ? sort.direction === 'asc'
      ? 'ascending'
      : 'descending'
    : 'none';

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSort(column);
    }
  };

  return (
    <TableHead
      aria-sort={ariaSort}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className={cn(
        'text-[10px] font-semibold uppercase tracking-wider py-3 h-auto select-none cursor-pointer hover:text-foreground transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
        isActive ? 'text-foreground' : 'text-muted-foreground',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        className,
      )}
      onClick={() => onSort(column)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {indicator ? (
          <span className="text-[10px] font-bold">{indicator.trim()}</span>
        ) : (
          <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-40 transition-opacity" />
        )}
      </span>
    </TableHead>
  );
}
