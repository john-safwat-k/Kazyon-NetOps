import * as React from 'react';

export type IconName = 'dashboard' | 'board' | 'list' | 'replication' | 'alert' | 'mail' | 'terminal' | 'store' | 'users' | 'settings' | 'search' | 'clock' | 'ticket' | 'bot' | 'pause' | 'plus' | 'filter' | 'download' | 'play' | 'bell' | 'chevron' | 'sun' | 'moon' | 'x';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual weight. One primary per view. */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'md' | 'sm';
  icon?: IconName;
}
export interface BadgeProps { tone?: 'neutral' | 'brand' | 'good' | 'warning' | 'critical' | 'info' | 'outline'; children?: React.ReactNode; }
export interface IspBadgeProps { isp: 'NOOR' | 'ORANGE' | 'WE'; /** ISP case / request number */ caseRef?: string; }
export interface StatusPillProps { label: 'IP1' | 'IP2' | '4G' | string; state: 'up' | 'down' | 'hub' | 'skip'; title?: string; }
export interface SlaTimerProps { /** negative = overdue */ minutesLeft: number; /** 120 welcome, 300 follow-up */ totalMinutes?: number; label?: string; }
export interface KpiCardProps { label: string; value: React.ReactNode; icon?: IconName; delta?: string; hint?: string; tone?: 'default' | 'warning' | 'critical'; }
export interface Ticket {
  id: string; priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'; branch: string; region: string;
  failure?: string; isp: 'NOOR' | 'ORANGE' | 'WE'; caseRef?: string;
  checks?: [string, StatusPillProps['state']][]; sla?: [number, number]; note?: string; aiPaused?: boolean;
}
export interface TicketCardProps { ticket: Ticket; }
export interface HealthBarProps { services: { name: string; detail?: string; state?: 'ok' | 'degraded' | 'down' }[]; }
export interface BarChartProps { data: { label: string; value: number; hint?: string }[]; unit?: string; max?: number; }
export interface AppShellProps { active?: string; /** nav label → link (e.g. a prototype screen) */ hrefs?: Record<string, string>; theme?: 'light' | 'dark'; onToggleTheme?: () => void; env?: string; initials?: string; children?: React.ReactNode; style?: React.CSSProperties; }
export interface DashboardScreenProps { style?: React.CSSProperties; }
export interface KanbanBoardProps { style?: React.CSSProperties; }

export declare function Button(p: ButtonProps): JSX.Element;
export declare function Badge(p: BadgeProps): JSX.Element;
export declare function IspBadge(p: IspBadgeProps): JSX.Element;
export declare function StatusPill(p: StatusPillProps): JSX.Element;
export declare function SlaTimer(p: SlaTimerProps): JSX.Element;
export declare function KpiCard(p: KpiCardProps): JSX.Element;
export declare function TicketCard(p: TicketCardProps): JSX.Element;
export declare function HealthBar(p: HealthBarProps): JSX.Element;
export declare function BarChart(p: BarChartProps): JSX.Element;
export declare function AppShell(p: AppShellProps): JSX.Element;
export declare function DashboardScreen(p: DashboardScreenProps): JSX.Element;
export declare function KanbanBoard(p: KanbanBoardProps): JSX.Element;
