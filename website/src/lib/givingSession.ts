export const SESSION_STEPS = ['gather', 'explore', 'decide', 'recap'] as const;
export type SessionStep = (typeof SESSION_STEPS)[number];

export function nextStep(s: SessionStep): SessionStep {
  const i = SESSION_STEPS.indexOf(s);
  return SESSION_STEPS[Math.min(i + 1, SESSION_STEPS.length - 1)];
}
export function prevStep(s: SessionStep): SessionStep {
  const i = SESSION_STEPS.indexOf(s);
  return SESSION_STEPS[Math.max(i - 1, 0)];
}
export function isLastStep(s: SessionStep): boolean {
  return s === SESSION_STEPS[SESSION_STEPS.length - 1];
}
