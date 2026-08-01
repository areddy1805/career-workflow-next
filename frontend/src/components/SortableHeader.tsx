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

  return (
    <TableHead
      className={cn(
        'text-[10px] font-semibold uppercase tracking-wider py-3 h-auto select-none cursor-pointer hover:text-foreground transition-colors group',
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
