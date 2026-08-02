import { Bot } from 'lucide-react';
import CopilotPlaceholder from './CopilotPlaceholder';

export default function Assistant() {
  return (
    <CopilotPlaceholder
      icon={Bot}
      title="Assistant"
      subtitle="Controlled browser session"
      note="The assistant panel ships with PH6."
    />
  );
}
