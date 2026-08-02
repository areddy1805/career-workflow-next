import { Send } from 'lucide-react';
import CopilotPlaceholder from './CopilotPlaceholder';

export default function Apply() {
  return (
    <CopilotPlaceholder
      icon={Send}
      title="Apply"
      subtitle="Application workspace wizard"
      note="The workspace wizard ships with PH6."
    />
  );
}
