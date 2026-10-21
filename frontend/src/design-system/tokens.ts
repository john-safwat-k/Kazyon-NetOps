/**
 * Kazyon NetOps Design System — Token definitions & mappings.
 * Source of truth: design/kazyon-netops-design-system/tokens/tokens.json
 */

export type ThemeMode = "light" | "dark";

export type BadgeTone =
  | "neutral"
  | "brand"
  | "good"
  | "warning"
  | "critical"
  | "info"
  | "outline";

export type IspName = "NOOR" | "ORANGE" | "WE";

export type TicketPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type CheckState = "up" | "down" | "hub" | "skip";

export type HealthServiceState = "ok" | "degraded" | "down";

export type KpiTone = "default" | "warning" | "critical";

export const PRIORITY_TONE: Record<TicketPriority, BadgeTone> = {
  CRITICAL: "critical",
  HIGH: "warning",
  MEDIUM: "brand",
  LOW: "neutral",
};

export const COLOR_TOKENS = {
  brand500: "var(--brand-500)",
  brand600: "var(--brand-600)",
  brand700: "var(--brand-700)",
  brandText: "var(--brand-text)",
  brand100: "var(--brand-100)",
  brand50: "var(--brand-50)",
  onBrand: "var(--on-brand)",
  surface000: "var(--surface-000)",
  surface100: "var(--surface-100)",
  surface200: "var(--surface-200)",
  ink: "var(--ink)",
  inkMuted: "var(--ink-muted)",
  border: "var(--border)",
  borderStrong: "var(--border-strong)",
  focus: "var(--focus)",
  good: "var(--good)",
  goodBg: "var(--good-bg)",
  warning: "var(--warning)",
  warningBg: "var(--warning-bg)",
  critical: "var(--critical)",
  criticalBg: "var(--critical-bg)",
  info: "var(--info)",
  infoBg: "var(--info-bg)",
  termBg: "var(--term-bg)",
  termInk: "var(--term-ink)",
} as const;

export const SPACING_TOKENS = {
  space1: "var(--space-1)", // 4px
  space2: "var(--space-2)", // 8px
  space3: "var(--space-3)", // 12px
  space4: "var(--space-4)", // 16px
  space6: "var(--space-6)", // 24px
  space8: "var(--space-8)", // 32px
} as const;

export const RADIUS_TOKENS = {
  sm: "var(--radius-sm)", // 6px
  md: "var(--radius-md)", // 10px
  lg: "var(--radius-lg)", // 14px
  pill: "var(--radius-pill)", // 999px
} as const;
