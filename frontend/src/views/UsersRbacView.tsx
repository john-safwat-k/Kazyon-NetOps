import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppShell,
  Badge,
  BadgeTone,
  Button,
  ThemeMode,
} from "../design-system";
import {
  ApiError,
  authApi,
  PermissionCatalogDTO,
  RoleDTO,
  rolesApi,
  UserDTO,
  usersApi,
} from "../lib/api";
import { getUserInitials, useAuth } from "../lib/auth";

export interface UsersRbacViewProps {
  theme: ThemeMode;
  onToggleTheme: () => void;
  onNavigate: (label: string) => void;
  env: string;
  canAccessNav?: (label: string) => boolean;
}

type ModalMode = "invite" | "role" | "edit" | "reset_password" | null;

const DEFAULT_MATRIX_ACTIONS = ["read", "create", "update", "delete", "execute"];

function formatRoleLabel(roleName: string, isSuperAdmin: boolean, roles: RoleDTO[]): string {
  if (isSuperAdmin || roleName === "super_admin") return "Super Admin";
  const matched = roles.find((r) => r.slug === roleName);
  if (matched) return matched.display_name;
  if (roleName === "support_engineer") return "HQ Network Engineer";
  if (roleName === "viewer") return "Viewer / IT Manager";
  return roleName;
}

function getRoleBadgeTone(roleName: string, isSuperAdmin: boolean): BadgeTone {
  if (isSuperAdmin || roleName === "super_admin") return "brand";
  if (roleName === "viewer" || roleName.startsWith("viewer")) return "neutral";
  return "info";
}

function formatLastLogin(iso: string | null): string {
  if (!iso) return "Never";
  try {
    const dt = new Date(iso);
    const now = new Date();
    const isToday = dt.toDateString() === now.toDateString();
    const timeStr = dt.toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
    if (isToday) return `Today ${timeStr}`;
    const dateStr = dt.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
    });
    return `${dateStr} ${timeStr}`;
  } catch {
    return iso;
  }
}

export function UsersRbacView({
  theme,
  onToggleTheme,
  onNavigate,
  env,
  canAccessNav,
}: UsersRbacViewProps) {
  const { user: currentUser, logout, hasPermission, refreshUser } = useAuth();

  const [users, setUsers] = useState<UserDTO[]>([]);
  const [activeCount, setActiveCount] = useState<number>(0);
  const [suspendedCount, setSuspendedCount] = useState<number>(0);
  const [roles, setRoles] = useState<RoleDTO[]>([]);
  const [catalog, setCatalog] = useState<PermissionCatalogDTO | null>(null);
  const [selectedRoleSlug, setSelectedRoleSlug] = useState<string>("support_engineer");
  const [draftRolePerms, setDraftRolePerms] = useState<Record<string, Set<string>>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [savingMatrix, setSavingMatrix] = useState<boolean>(false);
  const [toast, setToast] = useState<{ text: string; tone: "good" | "critical" | "info" } | null>(
    null,
  );

  // Modal state
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [targetUser, setTargetUser] = useState<UserDTO | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalBusy, setModalBusy] = useState<boolean>(false);

  // Invite form state
  const [inviteDisplayName, setInviteDisplayName] = useState<string>("");
  const [inviteEmail, setInviteEmail] = useState<string>("");
  const [inviteRole, setInviteRole] = useState<string>("support_engineer");
  const [invitePassword, setInvitePassword] = useState<string>("Kz-7Q4m-29xT");

  // New Role form state
  const [newRoleName, setNewRoleName] = useState<string>("");
  const [newRoleBaseSlug, setNewRoleBaseSlug] = useState<string>("viewer");

  // Edit User form state
  const [editDisplayName, setEditDisplayName] = useState<string>("");
  const [editEmail, setEditEmail] = useState<string>("");
  const [editRole, setEditRole] = useState<string>("support_engineer");

  // Reset Password form state
  const [resetNewPassword, setResetNewPassword] = useState<string>("Kz-9X2p-84mR");

  const canManageUsers = hasPermission("users:create") || hasPermission("users:edit_permissions");
  const canManageRoles = hasPermission("roles:manage") || hasPermission("users:edit_permissions");

  const showToast = useCallback(
    (text: string, tone: "good" | "critical" | "info" = "info") => {
      setToast({ text, tone });
      window.setTimeout(() => {
        setToast((prev) => (prev?.text === text ? null : prev));
      }, 4000);
    },
    [],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [usersResp, rolesResp, catalogResp] = await Promise.all([
        usersApi.list({ limit: 100 }),
        rolesApi.list(),
        authApi.permissions(),
      ]);
      setUsers(usersResp.items);
      setActiveCount(usersResp.active_count);
      setSuspendedCount(usersResp.suspended_count);
      setRoles(rolesResp);
      setCatalog(catalogResp);

      const nextDraft: Record<string, Set<string>> = {};
      for (const r of rolesResp) {
        nextDraft[r.slug] = new Set(r.permissions);
      }
      setDraftRolePerms(nextDraft);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load users and roles";
      showToast(msg, "critical");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const activeRolePerms = useMemo(() => {
    return draftRolePerms[selectedRoleSlug] || new Set<string>();
  }, [draftRolePerms, selectedRoleSlug]);

  const isMatrixLocked = selectedRoleSlug === "super_admin" || !canManageRoles;

  function toggleMatrixPermission(permKey: string) {
    if (isMatrixLocked) return;
    setDraftRolePerms((prev) => {
      const currentSet = new Set(prev[selectedRoleSlug] || []);
      if (currentSet.has(permKey)) {
        currentSet.delete(permKey);
      } else {
        currentSet.add(permKey);
      }
      return {
        ...prev,
        [selectedRoleSlug]: currentSet,
      };
    });
  }

  function handleDiscardMatrix() {
    const nextDraft: Record<string, Set<string>> = {};
    for (const r of roles) {
      nextDraft[r.slug] = new Set(r.permissions);
    }
    setDraftRolePerms(nextDraft);
    showToast("Discarded unsaved permission changes", "info");
  }

  async function handleSaveMatrix() {
    if (isMatrixLocked) return;
    setSavingMatrix(true);
    try {
      const permsArray = Array.from(draftRolePerms[selectedRoleSlug] || []);
      const updatedRole = await rolesApi.update(selectedRoleSlug, {
        permissions: permsArray,
        sync_assigned_users: true,
      });
      setRoles((prev) =>
        prev.map((r) => (r.slug === updatedRole.slug ? updatedRole : r)),
      );
      setDraftRolePerms((prev) => ({
        ...prev,
        [updatedRole.slug]: new Set(updatedRole.permissions),
      }));
      await loadData();
      await refreshUser();
      showToast(`Saved permissions for ${updatedRole.display_name}`, "good");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to save permissions";
      showToast(msg, "critical");
    } finally {
      setSavingMatrix(false);
    }
  }

  function openInviteModal() {
    setModalError(null);
    setInviteDisplayName("");
    setInviteEmail("");
    setInviteRole("support_engineer");
    setInvitePassword("Kz-7Q4m-29xT");
    setModalMode("invite");
  }

  function openNewRoleModal() {
    setModalError(null);
    setNewRoleName("");
    setNewRoleBaseSlug("viewer");
    setModalMode("role");
  }

  function openEditUserModal(u: UserDTO) {
    setModalError(null);
    setTargetUser(u);
    setEditDisplayName(u.display_name);
    setEditEmail(u.email);
    setEditRole(u.is_super_admin ? "super_admin" : u.role_name);
    setModalMode("edit");
  }

  function openResetPasswordModal(u: UserDTO) {
    setModalError(null);
    setTargetUser(u);
    setResetNewPassword("Kz-9X2p-84mR");
    setModalMode("reset_password");
  }

  function closeModal() {
    setModalMode(null);
    setTargetUser(null);
    setModalError(null);
  }

  async function handleModalSubmit() {
    setModalError(null);
    setModalBusy(true);
    try {
      if (modalMode === "invite") {
        if (!inviteDisplayName.trim() || !inviteEmail.trim() || !invitePassword.trim()) {
          setModalError("Please fill in display name, email, and temporary password.");
          setModalBusy(false);
          return;
        }
        const created = await usersApi.create({
          display_name: inviteDisplayName.trim(),
          email: inviteEmail.trim(),
          role_name: inviteRole,
          is_super_admin: inviteRole === "super_admin",
          password: invitePassword,
        });
        closeModal();
        await loadData();
        showToast(`Created user ${created.display_name} (${created.email})`, "good");
      } else if (modalMode === "role") {
        if (!newRoleName.trim()) {
          setModalError("Please enter a role name.");
          setModalBusy(false);
          return;
        }
        const createdRole = await rolesApi.create({
          display_name: newRoleName.trim(),
          base_role_slug: newRoleBaseSlug,
        });
        closeModal();
        await loadData();
        setSelectedRoleSlug(createdRole.slug);
        showToast(`Created role ${createdRole.display_name}`, "good");
      } else if (modalMode === "edit" && targetUser) {
        const updated = await usersApi.update(targetUser.id, {
          display_name: editDisplayName.trim(),
          email: editEmail.trim(),
          role_name: editRole,
          is_super_admin: editRole === "super_admin",
        });
        closeModal();
        await loadData();
        await refreshUser();
        showToast(`Updated ${updated.display_name}`, "good");
      } else if (modalMode === "reset_password" && targetUser) {
        await usersApi.resetPassword(targetUser.id, resetNewPassword);
        closeModal();
        showToast(`Reset password for ${targetUser.display_name}`, "good");
      }
    } catch (err) {
      setModalError(err instanceof ApiError ? err.message : "Operation failed");
    } finally {
      setModalBusy(false);
    }
  }

  async function handleToggleSuspend(u: UserDTO) {
    try {
      const updated = await usersApi.update(u.id, { is_active: !u.is_active });
      await loadData();
      showToast(
        `${updated.is_active ? "Reactivated" : "Suspended"} ${updated.display_name}`,
        updated.is_active ? "good" : "info",
      );
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Unable to update user status",
        "critical",
      );
    }
  }

  const matrixActions = catalog?.matrix_actions || DEFAULT_MATRIX_ACTIONS;
  const matrixResources = catalog?.resources || [];

  const modalTitle =
    modalMode === "invite"
      ? "Invite user"
      : modalMode === "role"
        ? "New role"
        : modalMode === "edit"
          ? `Edit ${targetUser?.display_name ?? "user"}`
          : `Reset password · ${targetUser?.display_name ?? ""}`;

  const modalSub =
    modalMode === "invite"
      ? "They get an account with the assigned role and temporary password."
      : modalMode === "role"
        ? "Roles group permissions; assign them to users."
        : modalMode === "edit"
          ? "Update profile details and assigned RBAC role."
          : "Assign a new password for this user.";

  const modalCta =
    modalMode === "invite"
      ? "Send invite"
      : modalMode === "role"
        ? "Create role"
        : modalMode === "edit"
          ? "Save user"
          : "Reset password";

  return (
    <AppShell
      active="Users & Roles"
      theme={theme}
      onToggleTheme={onToggleTheme}
      onNavigate={onNavigate}
      env={env}
      initials={getUserInitials(currentUser?.display_name, currentUser?.username)}
      userDisplayName={currentUser?.display_name}
      userRoleLabel={
        currentUser
          ? formatRoleLabel(currentUser.role_name, currentUser.is_super_admin, roles)
          : undefined
      }
      onLogout={logout}
      canAccessNav={canAccessNav}
      style={{ minHeight: 1060 }}
    >
      <div className="kz-page-hd">
        <div>
          <h1>Users, Roles &amp; Permissions</h1>
          <p>
            Super Admin only · permissions are granted per resource and action
            (resource:action)
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className="kz-btn kz-btn-secondary"
            disabled={!canManageRoles}
            onClick={openNewRoleModal}
          >
            + New role
          </button>
          <button
            type="button"
            className="kz-btn kz-btn-primary"
            disabled={!canManageUsers}
            onClick={openInviteModal}
          >
            + Invite user
          </button>
        </div>
      </div>

      {toast ? (
        <div
          role="status"
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            background:
              toast.tone === "critical"
                ? "var(--critical-bg)"
                : toast.tone === "good"
                  ? "var(--good-bg)"
                  : "var(--info-bg)",
            color:
              toast.tone === "critical"
                ? "var(--critical)"
                : toast.tone === "good"
                  ? "var(--good)"
                  : "var(--info)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {toast.text}
        </div>
      ) : null}

      {modalMode ? (
        <div className="kz-modal-scrim">
          <div
            role="dialog"
            aria-modal="true"
            aria-label={modalTitle}
            className="kz-card"
            style={{
              width: "100%",
              maxWidth: 520,
              boxShadow: "var(--shadow-raised)",
            }}
          >
            <div className="kz-card-hd">
              <div>
                <h2>{modalTitle}</h2>
                <p>{modalSub}</p>
              </div>
              <button
                type="button"
                className="kz-btn kz-btn-ghost kz-btn-sm"
                aria-label="Close"
                onClick={closeModal}
              >
                ✕
              </button>
            </div>

            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 14 }}
            >
              {modalError ? (
                <div
                  role="alert"
                  style={{
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: "var(--critical-bg)",
                    color: "var(--critical)",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  {modalError}
                </div>
              ) : null}

              {modalMode === "invite" ? (
                <>
                  <label className="kz-field">
                    Display name
                    <input
                      placeholder="Full name"
                      value={inviteDisplayName}
                      onChange={(e) => setInviteDisplayName(e.target.value)}
                    />
                  </label>
                  <label className="kz-field">
                    Kazyon email
                    <input
                      type="email"
                      placeholder="name@kazyon.com"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                    />
                  </label>
                  <label className="kz-field">
                    Role
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                    >
                      {roles.map((r) => (
                        <option key={r.slug} value={r.slug}>
                          {r.display_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="kz-field">
                    Temporary password
                    <input
                      value={invitePassword}
                      onChange={(e) => setInvitePassword(e.target.value)}
                      className="kz-mono"
                    />
                    <small>The user must change it at first sign-in.</small>
                  </label>
                </>
              ) : null}

              {modalMode === "role" ? (
                <>
                  <label className="kz-field">
                    Role name
                    <input
                      placeholder="e.g. Regional IT Liaison"
                      value={newRoleName}
                      onChange={(e) => setNewRoleName(e.target.value)}
                    />
                  </label>
                  <label className="kz-field">
                    Start from
                    <select
                      value={newRoleBaseSlug}
                      onChange={(e) => setNewRoleBaseSlug(e.target.value)}
                    >
                      <option value="viewer">Viewer / Auditor</option>
                      <option value="support_engineer">Network Engineer</option>
                      <option value="empty">Empty (no permissions)</option>
                    </select>
                  </label>
                  <p className="kz-tcard-meta" style={{ margin: 0 }}>
                    You can fine-tune each resource:action in the matrix after
                    creating it.
                  </p>
                </>
              ) : null}

              {modalMode === "edit" ? (
                <>
                  <label className="kz-field">
                    Display name
                    <input
                      value={editDisplayName}
                      onChange={(e) => setEditDisplayName(e.target.value)}
                    />
                  </label>
                  <label className="kz-field">
                    Kazyon email
                    <input
                      type="email"
                      value={editEmail}
                      onChange={(e) => setEditEmail(e.target.value)}
                    />
                  </label>
                  <label className="kz-field">
                    Role
                    <select
                      value={editRole}
                      onChange={(e) => setEditRole(e.target.value)}
                    >
                      {roles.map((r) => (
                        <option key={r.slug} value={r.slug}>
                          {r.display_name}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              ) : null}

              {modalMode === "reset_password" ? (
                <label className="kz-field">
                  New temporary password
                  <input
                    value={resetNewPassword}
                    onChange={(e) => setResetNewPassword(e.target.value)}
                    className="kz-mono"
                  />
                  <small>
                    Provide this password to {targetUser?.display_name}.
                  </small>
                </label>
              ) : null}
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 8,
                padding: "0 16px 16px",
              }}
            >
              <button
                type="button"
                className="kz-btn kz-btn-secondary"
                onClick={closeModal}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={modalBusy}
                className="kz-btn kz-btn-primary"
                onClick={() => void handleModalSubmit()}
              >
                {modalBusy ? "Working…" : modalCta}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <section className="kz-card" style={{ overflow: "hidden" }}>
        <div className="kz-card-hd" style={{ paddingBottom: 12 }}>
          <h2>Users</h2>
          <span className="kz-tcard-meta">
            {loading
              ? "Loading users…"
              : `${users.length} users · ${activeCount} active · ${suspendedCount} suspended`}
          </span>
        </div>
        <div className="kz-scroll-x">
          <table className="kz-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last sign-in</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const ini = getUserInitials(u.display_name, u.username);
                const roleLabel = formatRoleLabel(
                  u.role_name,
                  u.is_super_admin,
                  roles,
                );
                const roleTone = getRoleBadgeTone(u.role_name, u.is_super_admin);
                const isSelf = currentUser?.id === u.id;
                return (
                  <tr key={u.id}>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          gap: 10,
                          alignItems: "center",
                        }}
                      >
                        <span
                          className="kz-avatar"
                          style={{ width: 28, height: 28, fontSize: 11 }}
                        >
                          {ini}
                        </span>
                        <div>
                          <b className="kz-nowrap">{u.display_name}</b>
                          <div className="kz-tcard-meta kz-mono">
                            @{u.username}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="kz-tcard-meta kz-nowrap">{u.email}</td>
                    <td>
                      <Badge tone={roleTone}>{roleLabel}</Badge>
                    </td>
                    <td>
                      <Badge tone={u.is_active ? "good" : "critical"}>
                        {u.is_active ? "Active" : "Suspended"}
                      </Badge>
                    </td>
                    <td className="kz-num kz-nowrap">
                      {formatLastLogin(u.last_login_at)}
                    </td>
                    <td className="kz-nowrap">
                      <button
                        type="button"
                        className="kz-btn kz-btn-ghost kz-btn-sm"
                        disabled={!canManageUsers}
                        onClick={() => openEditUserModal(u)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="kz-btn kz-btn-ghost kz-btn-sm"
                        disabled={!canManageUsers}
                        onClick={() => openResetPasswordModal(u)}
                      >
                        Reset password
                      </button>
                      <button
                        type="button"
                        className="kz-btn kz-btn-ghost kz-btn-sm"
                        disabled={!canManageUsers || isSelf}
                        style={{ color: "var(--critical)" }}
                        onClick={() => void handleToggleSuspend(u)}
                      >
                        {u.is_active ? "Suspend" : "Reactivate"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="kz-card" style={{ overflow: "hidden" }}>
        <div
          className="kz-card-hd"
          style={{ flexWrap: "wrap", paddingBottom: 12 }}
        >
          <div>
            <h2>Permission matrix</h2>
            <p>
              Click a cell to grant or revoke. Changes apply on save and sync
              users assigned to that role.
            </p>
          </div>
          <div className="kz-seg" role="group" aria-label="Role">
            {roles.map((r) => (
              <button
                key={r.slug}
                type="button"
                className={r.slug === selectedRoleSlug ? "on" : ""}
                onClick={() => setSelectedRoleSlug(r.slug)}
              >
                {r.display_name}
              </button>
            ))}
          </div>
        </div>
        <div className="kz-scroll-x">
          <table className="kz-table">
            <thead>
              <tr>
                <th>Resource</th>
                {matrixActions.map((act) => (
                  <th key={act} style={{ textAlign: "center" }}>
                    {act}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrixResources.map((row) => (
                <tr key={row.resource}>
                  <td>
                    <span className="kz-mono" style={{ fontWeight: 700 }}>
                      {row.resource}:*
                    </span>
                    <div className="kz-tcard-meta">{row.description}</div>
                  </td>
                  {matrixActions.map((act) => {
                    const permKey = `${row.resource}:${act}`;
                    const isNa = row.not_applicable_actions.includes(act);
                    const isOn =
                      selectedRoleSlug === "super_admin" ||
                      activeRolePerms.has(permKey);
                    return (
                      <td key={act} style={{ textAlign: "center" }}>
                        {isNa ? (
                          <span
                            className="kz-muted"
                            aria-label="Not applicable"
                          >
                            —
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => toggleMatrixPermission(permKey)}
                            aria-pressed={isOn}
                            aria-label={`${isOn ? "Revoke" : "Grant"} ${permKey}`}
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: 6,
                              cursor: isMatrixLocked
                                ? "not-allowed"
                                : "pointer",
                              font: "700 14px var(--font-sans)",
                              border: `1.5px solid ${
                                isOn
                                  ? "var(--brand-600)"
                                  : "var(--border-strong)"
                              }`,
                              background: isOn
                                ? "var(--brand-600)"
                                : "var(--surface-000)",
                              color: "var(--on-brand)",
                            }}
                          >
                            {isOn ? "✓" : ""}
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            padding: "12px 16px",
            borderTop: "1px solid var(--border)",
          }}
        >
          <Button
            variant="secondary"
            size="sm"
            disabled={isMatrixLocked || savingMatrix}
            onClick={handleDiscardMatrix}
          >
            Discard
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={isMatrixLocked || savingMatrix}
            onClick={() => void handleSaveMatrix()}
          >
            {savingMatrix ? "Saving…" : "Save permissions"}
          </Button>
        </div>
      </section>
    </AppShell>
  );
}
