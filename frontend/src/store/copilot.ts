import { create } from 'zustand';

/**
 * Workspace client state (docs/application_copilot/07_UI.md §5).
 * Skeleton for CP-0-05; step flow is the frozen 5-step wizard (§3.2).
 * CP-6-03 added the wizard session binding (opportunityId/sessionId) and
 * the answers inline-edit view state (§3.2 step 2).
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

  // ─── CP-6-03 wizard session binding (07_UI §3.2) ─────────────────────
  /** Opportunity the wizard is bound to; null until a session exists. */
  opportunityId: string | null;
  /** Active workspace session for `opportunityId`. */
  sessionId: string | null;
  /** Bind the wizard to a created session (see Apply.tsx mount flow). */
  setSession: (opportunityId: string, sessionId: string) => void;

  /** Answers step: question_fp currently in inline edit (null = none). */
  editingAnswerFp: string | null;
  setEditingAnswerFp: (fp: string | null) => void;
}

const initialStep: WorkspaceStep = 'brief';

export const useCopilotStore = create<CopilotState>()((set) => ({
  step: initialStep,
  setStep: (step) => set({ step }),
  reset: () =>
    set({
      step: initialStep,
      opportunityId: null,
      sessionId: null,
      editingAnswerFp: null,
    }),
  opportunityId: null,
  sessionId: null,
  setSession: (opportunityId, sessionId) => set({ opportunityId, sessionId }),
  editingAnswerFp: null,
  setEditingAnswerFp: (fp) => set({ editingAnswerFp: fp }),
}));
