import { TrendingUp } from 'lucide-react';
import CopilotPlaceholder from './CopilotPlaceholder';

export default function Analytics() {
  return (
    <CopilotPlaceholder
      icon={TrendingUp}
      title="Analytics"
      subtitle="Funnel, conversion, and effort metrics"
      note="Analytics ships with PH8."
    />
  );
}
