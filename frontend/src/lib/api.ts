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
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
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
