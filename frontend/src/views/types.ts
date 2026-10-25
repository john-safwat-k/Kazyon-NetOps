import { ThemeMode } from "../design-system";

export interface ConsoleViewProps {
  theme: ThemeMode;
  onToggleTheme: () => void;
  onNavigate: (label: string) => void;
  onOpenTicket: (ticketNumber: string) => void;
  env: string;
  initials: string;
  userDisplayName: string;
  userRoleLabel: string;
  onLogout: () => void;
  canAccessNav: (label: string) => boolean;
}
