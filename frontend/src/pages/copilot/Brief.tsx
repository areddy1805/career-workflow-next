import { FileText } from 'lucide-react';
import CopilotPlaceholder from './CopilotPlaceholder';

export default function Brief() {
  return (
    <CopilotPlaceholder
      icon={FileText}
      title="Brief"
      subtitle="Application intelligence briefing"
      note="The Brief view ships with PH6."
    />
  );
}
