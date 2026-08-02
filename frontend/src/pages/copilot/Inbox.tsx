import { Inbox as InboxIcon } from 'lucide-react';
import CopilotPlaceholder from './CopilotPlaceholder';

export default function Inbox() {
  return (
    <CopilotPlaceholder
      icon={InboxIcon}
      title="Inbox"
      subtitle="Unified opportunity triage"
      note="Opportunity triage ships with PH6."
    />
  );
}
