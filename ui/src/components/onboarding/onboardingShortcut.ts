export function isOnboardingIntent(text: string, getStartedLabel: string): boolean {
  const t = text.trim().toLowerCase();
  return t === getStartedLabel.trim().toLowerCase();
}
