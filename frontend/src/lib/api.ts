/**
 * Typed HTTP API client for the Kazyon NetOps Console.
 * Automatically attaches Bearer JWT tokens and parses RFC 7807 problem-detail errors.
 */

export const AUTH_TOKEN_STORAGE_KEY = "kazyon-netops-auth-token";
export const AUTH_USER_STORAGE_KEY = "kazyon-netops-auth-user";

export interface UserDTO {
  id: number;
  username: string;
  email: string;
  display_name: string;
  role_name: string;
  is_super_admin: boolean;
  is_active: boolean;
  permissions: string[];
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TokenResponseDTO {
  access_token: string;
  token_type: string;
  expires_in_sec: number;
  user: UserDTO;
}

export interface UserListResponseDTO {
  items: UserDTO[];
  total: number;
  active_count: number;
  suspended_count: number;
  limit: number;
  offset: number;
}

export interface RoleDTO {
  id: number;
  slug: string;
  display_name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
  user_count: number;
  created_at: string;
  updated_at: string;
}

export interface PermissionResourceMetaDTO {
  resource: string;
  description: string;
  actions: string[];
  not_applicable_actions: string[];
  domain_permissions: string[];
}

export interface PermissionCatalogDTO {
  all_permissions: string[];
  matrix_actions: string[];
  resources: PermissionResourceMetaDTO[];
}

export interface AuditLogDTO {
  id: number;
  actor_user_id: number | null;
  actor_username: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  summary: string;
  details_json: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogListResponseDTO {
  items: AuditLogDTO[];
  total: number;
  limit: number;
  offset: number;
}

export type IspNameDTO = "NOOR" | "ORANGE" | "WE";
export type PriorityDTO = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type CheckStateDTO = "up" | "down" | "hub" | "skip";

export interface KanbanTicketCardDTO {
  id: string;
  ticket_db_id: number;
  priority: PriorityDTO;
  branch: string;
  branch_code: string;
  region: string;
  failure?: string | null;
  failure_code?: string | null;
  trigger: string;
  isp: IspNameDTO;
  caseRef?: string | null;
  checks?: [string, CheckStateDTO][] | null;
  sla?: [number, number] | null;
  note?: string | null;
  aiPaused: boolean;
  status: string;
  raw_status: string;
  opened: string;
  mttr: string;
  col: number;
}

export interface TimelineEventDTO {
  id: number;
  time: string;
  color: string;
  title: string;
  actor: string;
  detail: string;
  event_type: string;
}

export interface ThreadReplyItemDTO {
  index: number;
  is_latest: boolean;
  header: string;
  sender_hint?: string | null;
  sent_at_hint?: string | null;
  body: string;
}

export interface TicketEmailItemDTO {
  id: number;
  from_addr: string;
  to_addr: string;
  cc_addr?: string;
  when: string;
  direction: string;
  thread_type: string;
  subject: string;
  body: string;
  outbound: boolean;
  classification_label?: string | null;
  attachments: Array<Record<string, unknown>>;
  thread_replies?: ThreadReplyItemDTO[];
}

export interface ProposedOutboundEmailDTO {
  thread_type: string;
  recipients: string[];
  cc?: string[];
  subject: string;
  body_text: string;
  classification_label?: string;
}

export interface PendingAdminActionDTO {
  action_label: string;
  summary: string;
  previous_status?: string;
  target_status?: string | null;
  transition_reason?: string;
  connection_failure_type?: string | null;
  isp_welcome_received?: boolean | null;
  isp_reference_number?: string | null;
  followup_minutes?: number | null;
  proposed_emails?: ProposedOutboundEmailDTO[];
  context_lines?: string[];
  requested_at?: string;
}

export interface TicketDetail360DTO {
  ticket_db_id: number;
  ticket_number: string;
  title: string;
  description?: string | null;
  status: string;
  stage_label: string;
  priority: PriorityDTO;
  trigger_source: string;
  ai_automation_enabled: boolean;
  opened_at: string;
  sender_email: string;
  site_contact_phone: string;
  isp_reference_number: string;
  isp_welcome_received: boolean;
  followup_count: number;
  sla_minutes_left: number;
  sla_total_minutes: number;
  sla_summary_text: string;
  escalation_reason?: string | null;
  pending_admin_action?: PendingAdminActionDTO | null;
  branch: {
    code: string;
    name: string;
    ip1: string;
    ip2: string;
    region: string;
    regional_it_email: string;
  };
  isp: {
    name: IspNameDTO;
    support_email: string;
    ll_circuit_id: string;
    backup_circuit_id: string;
    four_g_hub_ip: string;
  };
  vision: {
    has_photo: boolean;
    photo_filename: string;
    cables_plugged: boolean;
    power_led_on: boolean;
    wan_led_on: boolean;
    confidence: number;
    summary: string;
  };
  events: TimelineEventDTO[];
  diagnostic_runs: Array<{
    id: number;
    label: string;
    when: string;
    ms: string;
    open: boolean;
    result: string;
    diagnosis_code: string;
    tone: string;
    checks: Array<{ label: string; state: CheckStateDTO }>;
    log: string;
  }>;
  branch_emails: TicketEmailItemDTO[];
  isp_emails: TicketEmailItemDTO[];
}

export interface DashboardSummaryDTO {
  range_key: string;
  range_label: string;
  total_branches?: number;
  regions_list?: string[];
  kpis: {
    open: number;
    review: number;
    welcome: number;
    followup: number;
    repl: number;
  };
  services: Array<{
    name: string;
    detail: string;
    state: "ok" | "degraded" | "down";
  }>;
  by_isp: Array<{ label: string; value: number; hint?: string }>;
  mttr_by_isp: Array<{ label: string; value: number }>;
  by_type: Array<{ label: string; value: number }>;
  by_region: Array<{ label: string; value: number; hint?: string }>;
  watchlist: Array<{
    id: string;
    branch: string;
    region: string;
    failure: string;
    isp: IspNameDTO;
    checks: Array<{ label: string; state: CheckStateDTO }>;
    stage: string;
    tone: string;
    left: number;
    total: number;
  }>;
}

export interface ReplicationReportItemDTO {
  id: number;
  subject: string;
  received: string;
  total: number;
  nu: number;
  notified: number;
  tone: "critical" | "warning" | "good";
  rows: Array<{
    id: string;
    name: string;
    region: string;
    last: string;
    biz: string;
    status: string;
    tone: "good" | "critical";
    mail: string;
    ticket: string;
  }>;
}

export interface EscalationItemDTO {
  key: string;
  ticket_number: string | null;
  email_id: number | null;
  reason: string;
  isp: IspNameDTO | null;
  case_ref: string | null;
  when: string;
  title: string;
  quote: string;
  from_addr: string;
  summary: string;
  engineer_email: string;
  primary_action: string;
  pending_admin_action?: PendingAdminActionDTO | null;
}

export interface MailboxTriageItemDTO {
  id: number;
  time: string;
  dir: "IN" | "OUT";
  dtone: "info" | "outline";
  thread_type?: string;
  who: string;
  from: string;
  to: string;
  cc?: string;
  subject: string;
  cls: string;
  ctone: string;
  ticket: string;
  ticket_status?: string;
  branch_code?: string;
  in_reply_to?: string;
  body: string;
  thread_reply_count?: number;
  thread_replies?: ThreadReplyItemDTO[];
  att: string;
  json: string;
  mid: string;
  headers: string;
}

export interface EmailLoopStatusDTO {
  background_loop_running: boolean;
  global_ai_kill_switch: boolean;
  poll_interval_sec: number;
  last_poll_at: string;
  seconds_since_last_poll: number;
  poll_count: number;
  inbound_count: number;
  outbound_count: number;
  open_isp_threads_count: number;
  awaiting_branch_threads_count: number;
  mailbox_account: string;
  smtp_host: string;
  smtp_port?: number;
  smtp_security?: SmtpSecurity;
  smtp_enabled?: boolean;
  smtp_credentials_configured?: boolean;
  test_redirect_email?: string;
  smtp_listener: SmtpListenerStatusDTO;
}

/** Inbound SMTP listener: the company mail server forwards branch / ISP mail to the agent. */
export interface SmtpListenerStatusDTO {
  enabled: boolean;
  running: boolean;
  host?: string;
  port?: number;
  allowed_clients?: string[];
  messages_accepted?: number;
  messages_rejected?: number;
  connections_refused?: number;
  last_received_at?: string | null;
  last_error?: string | null;
}

export interface EmailLoopOutboundItemDTO {
  id: number;
  thread_type: string;
  to: string;
  subject: string;
  classification_label: string;
  message_id: string;
  in_reply_to?: string | null;
}

export interface SandboxStageTraceItemDTO {
  step: number;
  name: string;
  status: "PASS" | "FAIL" | "WARN" | "SKIPPED" | "INFO";
  summary: string;
  detail: string;
}

export interface SandboxSuggestedNextStepDTO {
  scenario: string;
  role: "BRANCH" | "ISP";
  label: string;
  description: string;
}

export interface EmailLoopTriggerResponseDTO {
  email_id: number;
  filename: string;
  subject: string;
  sender: string;
  classification_label: string;
  trigger_type: string;
  action: string;
  branch_code?: string | null;
  isp_reference_number?: string | null;
  ticket_number: string;
  ticket_status?: string | null;
  correlation_method?: string;
  outbound_emails?: EmailLoopOutboundItemDTO[];
  actions_taken?: string[];
  triage?: Record<string, unknown>;
  stage_trace?: SandboxStageTraceItemDTO[];
  suggested_next_steps?: SandboxSuggestedNextStepDTO[];
}

export interface DiagnosticStepDetailDTO {
  step_number: number;
  step_name: string;
  target: string;
  status: "UP" | "DOWN" | "HUB_DETECTED" | "MPLS_DIRECT" | "SKIPPED";
  tone: "good" | "warning" | "critical" | "info" | "neutral";
  latency_or_hops: string;
  explanation: string;
}

export interface DiagnosticRunDTO {
  id: number;
  ticket_id: number | null;
  branch_code: string;
  branch_name?: string | null;
  branch_label?: string | null;
  isp_name: string;
  script_name?: string;
  ip_1?: string;
  ip_2?: string;
  ip_1_up?: boolean | null;
  ip_2_up?: boolean | null;
  ip_1_reachable?: boolean;
  ip_2_reachable?: boolean | null;
  ip_2_skipped?: boolean;
  four_g_hub_detected?: boolean | null;
  detected_hub_ip?: string | null;
  traceroute_ran?: boolean;
  matched_4g_hub_ip?: string | null;
  diagnosis_code: string;
  diagnosis_title?: string;
  diagnosis_meaning?: string;
  meaning?: string;
  root_cause?: string;
  responsible_team?: string;
  ai_workflow_action?: string;
  operator_action?: string;
  summary?: string;
  result_status: string;
  tone?: "good" | "warning" | "critical" | "info";
  checks: Array<{ label: string; state: CheckStateDTO }>;
  steps?: DiagnosticStepDetailDTO[];
  raw_output: string;
  duration_ms: number;
  trigger_source: string;
  executed_at: string;
}

export interface DiagnosticSuiteIspSummaryDTO {
  isp_name: string;
  total: number;
  pass_count: number;
  full_outage_count: number;
  four_g_count: number;
  lan_switch_count: number;
  health_pct: number;
}

export interface DiagnosticSuiteRegionSummaryDTO {
  region: string;
  total: number;
  pass_count: number;
  full_outage_count: number;
  four_g_count: number;
  lan_switch_count: number;
  health_pct: number;
}

export interface DiagnosticSuiteBranchItemDTO {
  branch_code: string;
  branch_name: string;
  region: string;
  isp_name: string;
  ip_1: string;
  ip_2: string;
  four_g_hub_ip: string | null;
  ll_circuit_id: string | null;
  backup_circuit_id: string | null;
  regional_it_email: string | null;
  ip_1_up: boolean;
  ip_2_up: boolean | null;
  ip_2_skipped: boolean;
  four_g_hub_detected: boolean;
  detected_hub_ip: string | null;
  result_status: string;
  diagnosis_code: string;
  diagnosis_title: string;
  meaning: string;
  root_cause: string;
  responsible_team: string;
  ai_workflow_action: string;
  operator_action: string;
  checks: Array<{ label: string; state: CheckStateDTO }>;
  steps: DiagnosticStepDetailDTO[];
  raw_output: string;
  duration_ms: number;
}

export interface DiagnosticSuiteReportDTO {
  suite_id: string;
  executed_at: string;
  duration_ms: number;
  scenario_mode: string;
  total_branches: number;
  pass_count: number;
  full_outage_count: number;
  four_g_count: number;
  lan_switch_count: number;
  health_pct: number;
  by_isp: DiagnosticSuiteIspSummaryDTO[];
  by_region: DiagnosticSuiteRegionSummaryDTO[];
  items: DiagnosticSuiteBranchItemDTO[];
}

export interface SandboxCatalogDTO {
  branches: Array<{
    code: string;
    name?: string;
    region?: string;
    label: string;
    ip1: string;
    ip2: string;
    isp: IspNameDTO;
    hub: string;
    ll_circuit_id?: string;
    backup_circuit_id?: string;
    regional_it_email?: string;
    default_result: string;
  }>;
  hub_ips: Record<string, string>;
  recent_runs: Array<{
    id: number;
    branch_code: string;
    when: string;
    diagnosis_code: string;
    tone: "good" | "warning" | "critical" | "info";
  }>;
}

export interface BranchDTO {
  id: number;
  branch_code: string;
  name: string;
  ip_1: string;
  ip_2: string;
  region: string | null;
  regional_it_email: string | null;
  isp_name: IspNameDTO;
  isp_contact_mail: string;
  four_g_hub_ip: string | null;
  ll_circuit_id: string | null;
  backup_circuit_id: string | null;
  isp_id: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BranchListResponseDTO {
  items: BranchDTO[];
  total: number;
  limit: number;
  offset: number;
  regions_count: Record<string, number>;
  isps_count: Record<string, number>;
}

export interface IspDTO {
  id: number;
  name: IspNameDTO;
  support_email: string;
  cc_emails: string[];
  four_g_hub_ip: string | null;
  welcome_sla_minutes: number;
  followup_sla_minutes: number;
  account_manager_email: string | null;
  escalation_template: string | null;
  is_active: boolean;
  store_count: number;
  created_at: string;
  updated_at: string;
}

export interface SeedRowPreviewDTO {
  action: "CREATED" | "UPDATED" | "UNCHANGED" | string;
  branch_code: string;
  name: string;
  region: string;
  ip_1: string;
  ip_2: string;
  isp_name: string;
  isp_contact_mail: string;
  regional_it_email: string;
  four_g_hub_ip: string | null;
  ll_circuit_id: string | null;
  backup_circuit_id: string | null;
}

export interface SeedResultSummaryDTO {
  dry_run: boolean;
  replace_existing?: boolean;
  source_filename: string;
  total_rows_parsed: number;
  unchanged_count: number;
  updated_count: number;
  created_count: number;
  deleted_count?: number;
  warnings_count: number;
  warnings: string[];
  by_isp: Record<string, number>;
  by_region: Record<string, number>;
  preview_rows?: SeedRowPreviewDTO[];
}

export type SmtpSecurity = "starttls" | "ssl" | "none";

export interface SmtpConnectionTestResult {
  ok: boolean;
  host: string;
  port: number;
  security: SmtpSecurity;
  authenticated: boolean;
  credentials_configured: boolean;
  stage: "config" | "connect" | "ehlo" | "tls" | "auth" | "sender" | "done";
  latency_ms: number;
  server_banner: string | null;
  error: string | null;
}

export interface VllmConnectionTestResult {
  ok: boolean;
  endpoint: string;
  configured_model: string;
  model_available: boolean;
  available_models: string[];
  latency_ms: number;
  error: string | null;
}

export interface SendTestEmailResult {
  ok: boolean;
  recipient: string;
  subject: string;
  message_id: string;
  latency_ms: number;
  error: string | null;
}

export interface SystemSettingsDTO {
  global_ai_kill_switch: boolean;
  mailbox_account: string;
  smtp_host: string;
  smtp_port: number;
  smtp_security: SmtpSecurity;
  smtp_enabled: boolean;
  smtp_username: string;
  /** True when SMTP login is configured in DB or environment (password never returned). */
  smtp_credentials_configured: boolean;
  smtp_password?: string;
  test_redirect_email: string;
  poll_interval_sec: number;
  vllm_endpoint: string;
  vllm_temperature: number;
  vllm_max_tokens: number;
  confidence_threshold: number;
  welcome_sla_minutes: number;
  followup_interval_minutes: number;
  max_chasers_before_human: number;
  max_outbound_emails_per_ticket_hour: number;
  ignore_auto_submitted: boolean;
  diagnostic_timeout_sec: number;
  ping_count: number;
  traceroute_max_hops: number;
  admin_notification_email: string;
  notify_admin_on_every_action: boolean;
  require_admin_approval_before_action: boolean;
  fallback_contacts: Array<{
    ini: string;
    email: string;
    role: string;
  }>;
}

export class ApiError extends Error {
  status: number;
  type: string;
  details: Record<string, unknown>;

  constructor(
    message: string,
    status: number,
    type = "ApiError",
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.type = type;
    this.details = details;
  }
}

export function getStoredToken(): string | null {
  try {
    return (
      window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ||
      window.sessionStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
    );
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null, persist = true): void {
  try {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    window.sessionStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    if (token) {
      const storage = persist ? window.localStorage : window.sessionStorage;
      storage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    }
  } catch {
    // Ignore storage errors in restricted environments
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers || {});
  if (
    !headers.has("Content-Type") &&
    options.body &&
    !(options.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  let data: unknown = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    const text = await response.text();
    data = { title: text || response.statusText };
  }

  if (!response.ok) {
    const errObj = (data || {}) as Record<string, unknown>;
    const title =
      (typeof errObj.title === "string" && errObj.title) ||
      (typeof errObj.detail === "string" && errObj.detail) ||
      `Request failed (${response.status})`;
    const type = typeof errObj.type === "string" ? errObj.type : "ApiError";
    const details =
      typeof errObj.details === "object" && errObj.details !== null
        ? (errObj.details as Record<string, unknown>)
        : {};
    throw new ApiError(title, response.status, type, details);
  }

  return data as T;
}

export const authApi = {
  login(username_or_email: string, password: string): Promise<TokenResponseDTO> {
    return apiRequest<TokenResponseDTO>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username_or_email, password }),
    });
  },
  me(): Promise<UserDTO> {
    return apiRequest<UserDTO>("/api/v1/auth/me");
  },
  changePassword(current_password: string, new_password: string): Promise<UserDTO> {
    return apiRequest<UserDTO>("/api/v1/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    });
  },
  permissions(): Promise<PermissionCatalogDTO> {
    return apiRequest<PermissionCatalogDTO>("/api/v1/auth/permissions");
  },
  auditLogs(limit = 50, offset = 0): Promise<AuditLogListResponseDTO> {
    return apiRequest<AuditLogListResponseDTO>(
      `/api/v1/auth/audit-logs?limit=${limit}&offset=${offset}`,
    );
  },
};

export const usersApi = {
  list(params?: {
    search?: string;
    role_name?: string;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<UserListResponseDTO> {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.role_name) qs.set("role_name", params.role_name);
    if (params?.is_active !== undefined) qs.set("is_active", String(params.is_active));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiRequest<UserListResponseDTO>(`/api/v1/users${suffix}`);
  },
  create(payload: {
    username?: string;
    email: string;
    display_name: string;
    password: string;
    role_name: string;
    is_super_admin?: boolean;
    is_active?: boolean;
    permissions?: string[];
  }): Promise<UserDTO> {
    return apiRequest<UserDTO>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  update(
    userId: number,
    payload: {
      username?: string;
      email?: string;
      display_name?: string;
      role_name?: string;
      is_super_admin?: boolean;
      is_active?: boolean;
    },
  ): Promise<UserDTO> {
    return apiRequest<UserDTO>(`/api/v1/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  updatePermissions(
    userId: number,
    payload: {
      permissions: string[];
      role_name?: string;
      is_super_admin?: boolean;
    },
  ): Promise<UserDTO> {
    return apiRequest<UserDTO>(`/api/v1/users/${userId}/permissions`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  resetPassword(userId: number, new_password: string): Promise<UserDTO> {
    return apiRequest<UserDTO>(`/api/v1/users/${userId}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ new_password }),
    });
  },
};

export const rolesApi = {
  list(): Promise<RoleDTO[]> {
    return apiRequest<RoleDTO[]>("/api/v1/roles");
  },
  create(payload: {
    slug?: string;
    display_name: string;
    description?: string;
    base_role_slug?: string;
    permissions?: string[];
  }): Promise<RoleDTO> {
    return apiRequest<RoleDTO>("/api/v1/roles", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  update(
    roleSlug: string,
    payload: {
      display_name?: string;
      description?: string;
      permissions?: string[];
      sync_assigned_users?: boolean;
    },
  ): Promise<RoleDTO> {
    return apiRequest<RoleDTO>(`/api/v1/roles/${encodeURIComponent(roleSlug)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  delete(roleSlug: string): Promise<void> {
    return apiRequest<void>(`/api/v1/roles/${encodeURIComponent(roleSlug)}`, {
      method: "DELETE",
    });
  },
};

export const dashboardApi = {
  summary(range: "24h" | "7d" | "30d" = "7d"): Promise<DashboardSummaryDTO> {
    return apiRequest<DashboardSummaryDTO>(
      `/api/v1/dashboard/summary?range=${encodeURIComponent(range)}`,
    );
  },
};

export const ticketsApi = {
  list(params?: {
    search?: string;
    isp?: string;
    region?: string;
    priority?: string;
    trigger?: string;
    failure_type?: string;
    ai_paused_only?: boolean;
  }): Promise<KanbanTicketCardDTO[]> {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.isp && params.isp !== "ALL") qs.set("isp", params.isp);
    if (params?.region && params.region !== "All") qs.set("region", params.region);
    if (params?.priority && params.priority !== "All") qs.set("priority", params.priority);
    if (params?.trigger && params.trigger !== "All") qs.set("trigger", params.trigger);
    if (params?.failure_type && params.failure_type !== "All") {
      qs.set("failure_type", params.failure_type);
    }
    if (params?.ai_paused_only) qs.set("ai_paused_only", "true");
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiRequest<KanbanTicketCardDTO[]>(`/api/v1/tickets${suffix}`);
  },
  createManual(payload: {
    branch_code: string;
    priority?: PriorityDTO;
    site_contact_phone?: string;
    trigger_source?: string;
    description?: string;
    run_diagnostics?: boolean;
    simulate_scenario?:
      | "LIVE_ICMP"
      | "AUTO"
      | "PASS"
      | "FULL_OUTAGE"
      | "LOCAL_LOOP_DOWN_ON_4G"
      | "INTERNAL_LAN_SWITCH";
  }): Promise<KanbanTicketCardDTO> {
    return apiRequest<KanbanTicketCardDTO>("/api/v1/tickets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  get360(ticketIdentifier: string): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}`,
    );
  },
  update(
    ticketIdentifier: string,
    payload: {
      status?: string;
      priority?: string;
      ai_automation_enabled?: boolean;
      isp_reference_number?: string;
      site_contact_phone?: string;
      kanban_col?: number;
    },
  ): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },
  addNote(ticketIdentifier: string, note: string): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/notes`,
      {
        method: "POST",
        body: JSON.stringify({ note }),
      },
    );
  },
  rerunDiagnostics(ticketIdentifier: string): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/rerun-diagnostics`,
      {
        method: "POST",
      },
    );
  },
  forceFollowup(ticketIdentifier: string): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/force-followup`,
      {
        method: "POST",
      },
    );
  },
  replyEmail(
    ticketIdentifier: string,
    payload: {
      thread_type: "BRANCH" | "ISP";
      body_text: string;
      subject?: string;
    },
  ): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/reply`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  escalateHuman(
    ticketIdentifier: string,
    payload: {
      target_email: string;
      reason: string;
      note: string;
    },
  ): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/escalate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  overrideVision(
    ticketIdentifier: string,
    payload: {
      cables_plugged: boolean;
      summary?: string;
    },
  ): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/override-vision`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  approveAction(ticketIdentifier: string): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/approve-action`,
      {
        method: "POST",
      },
    );
  },
  rejectAction(ticketIdentifier: string): Promise<TicketDetail360DTO> {
    return apiRequest<TicketDetail360DTO>(
      `/api/v1/tickets/${encodeURIComponent(ticketIdentifier)}/reject-action`,
      {
        method: "POST",
      },
    );
  },
};

export const replicationApi = {
  listReports(): Promise<ReplicationReportItemDTO[]> {
    return apiRequest<ReplicationReportItemDTO[]>("/api/v1/replication/reports");
  },
  parse(payload: {
    subject: string;
    html_content: string;
    dry_run: boolean;
  }): Promise<{
    subject: string;
    dry_run: boolean;
    total_rows_parsed: number;
    not_updated_count: number;
    tickets_created: number;
    emails_sent: number;
    duplicates_skipped: number;
    created_ticket_numbers: string[];
  }> {
    return apiRequest("/api/v1/replication/parse", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};

export const escalationsApi = {
  list(): Promise<EscalationItemDTO[]> {
    return apiRequest<EscalationItemDTO[]>("/api/v1/escalations");
  },
  convertEmailToTicket(emailId: number): Promise<{
    email_id: number;
    ticket_number: string;
    status: string;
  }> {
    return apiRequest(`/api/v1/escalations/convert-email/${emailId}`, {
      method: "POST",
    });
  },
};

export const emailsApi = {
  list(): Promise<MailboxTriageItemDTO[]> {
    return apiRequest<MailboxTriageItemDTO[]>("/api/v1/emails");
  },
  loopStatus(): Promise<EmailLoopStatusDTO> {
    return apiRequest<EmailLoopStatusDTO>("/api/v1/emails/loop-status");
  },
  pollNow(): Promise<{
    polled_at: string;
    messages_fetched: number;
    messages_ingested: number;
    sla_chaser: { chased_count: number; escalated_to_human_count?: number };
    poll_count: number;
  }> {
    return apiRequest("/api/v1/emails/poll-now", {
      method: "POST",
    });
  },
  triggerInLoop(payload: {
    scenario: string;
    role?: "BRANCH" | "ISP";
    ticket_number?: string;
    branch_code?: string;
    sender?: string;
    subject?: string;
    body_text?: string;
    in_reply_to?: string;
    attachments?: string[];
    diagnostic_scenario?: string;
  }): Promise<EmailLoopTriggerResponseDTO> {
    return apiRequest<EmailLoopTriggerResponseDTO>("/api/v1/emails/trigger", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  reclassify(emailId: number): Promise<Record<string, unknown>> {
    return apiRequest<Record<string, unknown>>(
      `/api/v1/emails/${emailId}/reclassify`,
      {
        method: "POST",
      },
    );
  },
  listInfoSamples(): Promise<string[]> {
    return apiRequest<string[]>("/api/v1/emails/info-samples");
  },
  simulateFile(file: File): Promise<EmailLoopTriggerResponseDTO> {
    const form = new FormData();
    form.append("file", file);
    return apiRequest<EmailLoopTriggerResponseDTO>("/api/v1/emails/simulate-eml", {
      method: "POST",
      body: form,
    });
  },
  simulateSample(sampleFilename: string): Promise<EmailLoopTriggerResponseDTO> {
    return apiRequest<EmailLoopTriggerResponseDTO>(
      `/api/v1/emails/simulate-eml?sample_filename=${encodeURIComponent(sampleFilename)}`,
      {
        method: "POST",
      },
    );
  },
};

export const diagnosticsApi = {
  sandboxCatalog(): Promise<SandboxCatalogDTO> {
    return apiRequest<SandboxCatalogDTO>("/api/v1/diagnostics/sandbox-catalog");
  },
  listRuns(params?: {
    ticket_id?: number;
    branch_code?: string;
    limit?: number;
  }): Promise<DiagnosticRunDTO[]> {
    const qs = new URLSearchParams();
    if (params?.ticket_id !== undefined) qs.set("ticket_id", String(params.ticket_id));
    if (params?.branch_code) qs.set("branch_code", params.branch_code);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiRequest<DiagnosticRunDTO[]>(`/api/v1/diagnostics/runs${suffix}`);
  },
  run(payload: {
    branch_code: string;
    ip_1?: string;
    ip_2?: string;
    isp_name?: string;
    four_g_hub_ip?: string;
    mode?: "full" | "ping_ip1" | "ping_ip2" | "traceroute";
    check_mode?: "FULL" | "PING_IP1" | "PING_IP2" | "TRACEROUTE";
    simulate_scenario?:
      | "LIVE_ICMP"
      | "AUTO"
      | "PASS"
      | "FULL_OUTAGE"
      | "LOCAL_LOOP_DOWN_ON_4G"
      | "INTERNAL_LAN_SWITCH";
    timeout_sec?: number;
    ping_count?: number;
    traceroute_max_hops?: number;
    ticket_id?: number;
    trigger_source?: string;
  }): Promise<DiagnosticRunDTO> {
    return apiRequest<DiagnosticRunDTO>("/api/v1/diagnostics/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  runSuite(payload?: {
    isp_name?: string;
    region?: string;
    search?: string;
    simulate_scenario?:
      | "LIVE_ICMP"
      | "AUTO"
      | "PASS"
      | "FULL_OUTAGE"
      | "LOCAL_LOOP_DOWN_ON_4G"
      | "INTERNAL_LAN_SWITCH";
    ping_count?: number;
    traceroute_max_hops?: number;
    limit?: number;
  }): Promise<DiagnosticSuiteReportDTO> {
    return apiRequest<DiagnosticSuiteReportDTO>("/api/v1/diagnostics/run-suite", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },
};

export const branchesApi = {
  list(params?: {
    search?: string;
    region?: string;
    isp_name?: string;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<BranchListResponseDTO> {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.region && params.region !== "All") qs.set("region", params.region);
    if (params?.isp_name && params.isp_name !== "All" && params.isp_name !== "ALL") {
      qs.set("isp_name", params.isp_name);
    }
    if (params?.is_active !== undefined) qs.set("is_active", String(params.is_active));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiRequest<BranchListResponseDTO>(`/api/v1/branches${suffix}`);
  },
  deriveIps(branchCode: string): Promise<{ branch_code: string; ip_1: string; ip_2: string }> {
    return apiRequest(`/api/v1/branches/derive-ips/${encodeURIComponent(branchCode)}`);
  },
  getByCode(branchCode: string): Promise<BranchDTO> {
    return apiRequest<BranchDTO>(`/api/v1/branches/by-code/${encodeURIComponent(branchCode)}`);
  },
  create(payload: {
    branch_code: string;
    name: string;
    region: string;
    ip_1?: string;
    ip_2?: string;
    regional_it_email?: string;
    isp_name: string;
    isp_contact_mail?: string;
    four_g_hub_ip?: string;
    ll_circuit_id?: string;
    backup_circuit_id?: string;
    is_active?: boolean;
  }): Promise<BranchDTO> {
    return apiRequest<BranchDTO>("/api/v1/branches", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  update(
    branchId: number,
    payload: {
      branch_code?: string;
      name?: string;
      region?: string;
      ip_1?: string;
      ip_2?: string;
      regional_it_email?: string;
      isp_name?: string;
      isp_contact_mail?: string;
      four_g_hub_ip?: string;
      ll_circuit_id?: string;
      backup_circuit_id?: string;
      is_active?: boolean;
    },
  ): Promise<BranchDTO> {
    return apiRequest<BranchDTO>(`/api/v1/branches/${branchId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  delete(branchId: number): Promise<void> {
    return apiRequest<void>(`/api/v1/branches/${branchId}`, {
      method: "DELETE",
    });
  },
  seedExcel(params?: {
    dry_run?: boolean;
    replace_existing?: boolean;
    file?: File | null;
  }): Promise<SeedResultSummaryDTO> {
    const qs = new URLSearchParams();
    qs.set("dry_run", params?.dry_run ? "true" : "false");
    if (params?.replace_existing) {
      qs.set("replace_existing", "true");
    }
    const form = params?.file ? new FormData() : undefined;
    if (form && params?.file) {
      form.append("file", params.file);
    }
    return apiRequest<SeedResultSummaryDTO>(
      `/api/v1/branches/seed-excel?${qs.toString()}`,
      {
        method: "POST",
        body: form,
      },
    );
  },
  async downloadTemplate(format: "csv" | "xlsx" = "csv"): Promise<void> {
    const token = getStoredToken();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`/api/v1/branches/template?format=${format}`, {
      headers,
    });
    if (!res.ok) throw new Error(`Failed to download template (${res.status})`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `kazyon-branches-template.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },
  async exportSheet(params?: {
    format?: "csv" | "xlsx";
    search?: string;
    region?: string;
    isp_name?: string;
  }): Promise<void> {
    const fmt = params?.format || "csv";
    const qs = new URLSearchParams();
    qs.set("format", fmt);
    if (params?.search) qs.set("search", params.search);
    if (params?.region && params.region !== "All") qs.set("region", params.region);
    if (params?.isp_name && params.isp_name !== "All" && params.isp_name !== "ALL") {
      qs.set("isp_name", params.isp_name);
    }
    const token = getStoredToken();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`/api/v1/branches/export?${qs.toString()}`, {
      headers,
    });
    if (!res.ok) throw new Error(`Failed to export branches (${res.status})`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `kazyon-branches-export.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export const ispsApi = {
  list(): Promise<IspDTO[]> {
    return apiRequest<IspDTO[]>("/api/v1/isps");
  },
  update(
    ispIdOrName: string | number,
    payload: {
      support_email?: string;
      cc_emails?: string[];
      four_g_hub_ip?: string;
      welcome_sla_minutes?: number;
      followup_sla_minutes?: number;
      account_manager_email?: string;
      escalation_template?: string;
      is_active?: boolean;
    },
  ): Promise<IspDTO> {
    return apiRequest<IspDTO>(
      `/api/v1/isps/${encodeURIComponent(String(ispIdOrName))}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  },
};

export const settingsApi = {
  get(): Promise<SystemSettingsDTO> {
    return apiRequest<SystemSettingsDTO>("/api/v1/settings");
  },
  update(payload: Partial<SystemSettingsDTO>): Promise<SystemSettingsDTO> {
    return apiRequest<SystemSettingsDTO>("/api/v1/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  testSmtp(payload: {
    smtp_host?: string;
    smtp_port?: number;
    smtp_security?: SmtpSecurity;
    smtp_username?: string;
    smtp_password?: string;
    mailbox_account?: string;
  }): Promise<SmtpConnectionTestResult> {
    return apiRequest<SmtpConnectionTestResult>("/api/v1/settings/test-smtp", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  sendTestEmail(payload?: {
    recipient?: string;
    subject?: string;
    body_text?: string;
    branch_code?: string;
  }): Promise<SendTestEmailResult> {
    return apiRequest<SendTestEmailResult>("/api/v1/settings/send-test-email", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },
  testVllm(payload: { vllm_endpoint?: string }): Promise<VllmConnectionTestResult> {
    return apiRequest<VllmConnectionTestResult>("/api/v1/settings/test-vllm", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
