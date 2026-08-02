import { create } from 'zustand';

/**
 * Workspace client state (docs/application_copilot/07_UI.md §5).
 * Skeleton for CP-0-05; step flow is the frozen 5-step wizard (§3.2).
 * The answers/assistant views are added by CP-6-03/CP-6-04.
 */

export const WORKSPACE_STEPS = [
  'brief',
  'answers',
  'resume',
  'assistant',
  'submit',
] as const;

export type WorkspaceStep = (typeof WORKSPACE_STEPS)[number];

interface CopilotState {
  step: WorkspaceStep;
  setStep: (step: WorkspaceStep) => void;
  reset: () => void;
}

const initialStep: WorkspaceStep = 'brief';

export const useCopilotStore = create<CopilotState>()((set) => ({
  step: initialStep,
  setStep: (step) => set({ step }),
  reset: () => set({ step: initialStep }),
}));
