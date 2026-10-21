import React, { useState } from "react";
import { ThemeMode } from "../design-system";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";

export interface LoginViewProps {
  theme: ThemeMode;
  onToggleTheme: () => void;
  envSlug?: string;
  apiReachable?: boolean;
}

export function LoginView({
  theme,
  onToggleTheme,
  envSlug = "dev",
  apiReachable = true,
}: LoginViewProps) {
  const { login } = useAuth();
  const [selectedEnv, setSelectedEnv] = useState<"PROD" | "DEV">(
    envSlug.toUpperCase() === "PROD" ? "PROD" : "DEV",
  );
  const [usernameOrEmail, setUsernameOrEmail] = useState<string>("admin");
  const [password, setPassword] = useState<string>("it-net-admin-change-me");
  const [keepSignedIn, setKeepSignedIn] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isDark = theme === "dark";
  const portLabel = selectedEnv === "PROD" ? "10.100.109.9:8084" : "10.100.109.9:8085";

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErrorMessage(null);
    setSubmitting(true);
    try {
      await login(usernameOrEmail.trim(), password, keepSignedIn);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Unable to sign in. Verify your credentials and backend connectivity.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="kz"
      data-theme={theme}
      style={{
        minHeight: "100vh",
        display: "flex",
        flexWrap: "wrap",
        background: "var(--surface-000)",
        color: "var(--ink)",
      }}
    >
      <aside
        style={{
          flex: "1 1 520px",
          minHeight: 360,
          background: "var(--brand-500)",
          color: "#1f1a17",
          padding: 48,
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          gap: 32,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "#1f1a17",
              color: "#f47a20",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 800,
              fontSize: 22,
            }}
          >
            K
          </span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 18, lineHeight: "22px" }}>
              Kazyon NetOps
            </div>
            <div style={{ fontSize: 13, lineHeight: "18px", fontWeight: 500 }}>
              HQ IT Infrastructure
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 16,
            maxWidth: 520,
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: 52,
              lineHeight: "54px",
              fontWeight: 800,
              letterSpacing: "-0.02em",
            }}
          >
            Every branch online. Every ISP on the clock.
          </h1>
          <p
            style={{
              margin: 0,
              fontSize: 16,
              lineHeight: "24px",
              fontWeight: 500,
            }}
          >
            The AI support agent triages the service mailbox, runs dual-ping and
            4G traceroute checks, escalates to NOOR, ORANGE and WE, and hands
            anything unusual to you.
          </p>
        </div>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <div
            style={{
              background: "var(--surface-000)",
              color: "var(--ink)",
              borderRadius: 14,
              padding: "14px 18px",
              minWidth: 140,
            }}
          >
            <div style={{ fontSize: 28, lineHeight: "32px", fontWeight: 800 }}>
              1,150
            </div>
            <div
              style={{
                fontSize: 12,
                lineHeight: "16px",
                fontWeight: 600,
                color: "var(--ink-muted)",
              }}
            >
              branches monitored
            </div>
          </div>
          <div
            style={{
              background: "var(--surface-000)",
              color: "var(--ink)",
              borderRadius: 14,
              padding: "14px 18px",
              minWidth: 140,
            }}
          >
            <div style={{ fontSize: 28, lineHeight: "32px", fontWeight: 800 }}>
              3
            </div>
            <div
              style={{
                fontSize: 12,
                lineHeight: "16px",
                fontWeight: 600,
                color: "var(--ink-muted)",
              }}
            >
              network providers
            </div>
          </div>
          <div
            style={{
              background: "var(--surface-000)",
              color: "var(--ink)",
              borderRadius: 14,
              padding: "14px 18px",
              minWidth: 140,
            }}
          >
            <div style={{ fontSize: 28, lineHeight: "32px", fontWeight: 800 }}>
              5
            </div>
            <div
              style={{
                fontSize: 12,
                lineHeight: "16px",
                fontWeight: 600,
                color: "var(--ink-muted)",
              }}
            >
              regions
            </div>
          </div>
        </div>
      </aside>

      <main
        style={{
          flex: "1 1 480px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "48px 24px",
          boxSizing: "border-box",
        }}
      >
        <form
          onSubmit={handleSubmit}
          style={{
            width: "100%",
            maxWidth: 400,
            display: "flex",
            flexDirection: "column",
            gap: 20,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div className="kz-seg" role="group" aria-label="Environment">
              {(["PROD", "DEV"] as const).map((e) => (
                <button
                  key={e}
                  type="button"
                  className={selectedEnv === e ? "on" : ""}
                  onClick={() => setSelectedEnv(e)}
                >
                  {e} {e === "PROD" ? ":8084" : ":8085"}
                </button>
              ))}
            </div>
            <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span className="kz-live">
                {apiReachable ? `API reachable · ${portLabel}` : "Checking API…"}
              </span>
              <button
                type="button"
                className="kz-btn kz-btn-ghost kz-btn-sm"
                onClick={onToggleTheme}
                aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
                aria-pressed={isDark}
              >
                {isDark ? "☀ Light" : "☾ Dark"}
              </button>
            </span>
          </div>

          <div>
            <h2
              style={{
                margin: "0 0 4px",
                fontSize: 28,
                lineHeight: "34px",
                fontWeight: 700,
              }}
            >
              Sign in
            </h2>
            <p
              style={{
                margin: 0,
                color: "var(--ink-muted)",
                fontSize: 14,
              }}
            >
              Use your Kazyon IT account.
            </p>
          </div>

          {errorMessage ? (
            <div
              role="alert"
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid var(--critical)",
                background: "var(--critical-bg)",
                color: "var(--critical)",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {errorMessage}
            </div>
          ) : null}

          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Username or email
            <input
              type="text"
              autoComplete="username"
              required
              value={usernameOrEmail}
              onChange={(e) => setUsernameOrEmail(e.target.value)}
              placeholder="admin or name@kazyon.com"
              style={{
                height: 44,
                padding: "0 12px",
                border: "1px solid var(--border-strong)",
                borderRadius: 10,
                font: "500 14px var(--font-sans)",
                color: "var(--ink)",
                background: "var(--surface-000)",
              }}
            />
          </label>

          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••"
              style={{
                height: 44,
                padding: "0 12px",
                border: "1px solid var(--border-strong)",
                borderRadius: 10,
                font: "500 14px var(--font-sans)",
                color: "var(--ink)",
                background: "var(--surface-000)",
              }}
            />
          </label>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: 13,
            }}
          >
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={keepSignedIn}
                onChange={(e) => setKeepSignedIn(e.target.checked)}
                style={{
                  accentColor: "var(--brand-600)",
                  width: 16,
                  height: 16,
                }}
              />
              Keep me signed in
            </label>
            <span className="kz-muted" style={{ fontSize: 12 }}>
              Reset via Super Admin
            </span>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="kz-btn kz-btn-primary"
            style={{
              height: 44,
              justifyContent: "center",
              fontSize: 15,
            }}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>

          <p
            style={{
              margin: 0,
              fontSize: 12,
              lineHeight: "18px",
              color: "var(--ink-muted)",
            }}
          >
            Access is granted by your Super Admin. Your role decides which pages
            and actions you see.
          </p>
        </form>
      </main>
    </div>
  );
}
