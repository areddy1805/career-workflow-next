import { History as HistoryIcon } from 'lucide-react';
import CopilotPlaceholder from './CopilotPlaceholder';

export default function History() {
  return (
    <CopilotPlaceholder
      icon={HistoryIcon}
      title="History"
      subtitle="Application session timeline"
      note="History ships with PH6."
    />
  );
}
