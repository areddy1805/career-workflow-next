import { Cog } from 'lucide-react';
import CopilotPlaceholder from './CopilotPlaceholder';

export default function Settings() {
  return (
    <CopilotPlaceholder
      icon={Cog}
      title="Settings"
      subtitle="Copilot thresholds and preferences"
      note="Settings ships with PH6."
    />
  );
}
