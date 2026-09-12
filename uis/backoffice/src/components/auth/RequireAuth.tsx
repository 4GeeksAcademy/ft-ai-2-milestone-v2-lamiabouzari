"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useIsAuthenticated } from "@/lib/auth";

interface RequireAuthProps {
  readonly children: React.ReactNode;
}

/**
 * Client-side guard for pages that require an authenticated session.
 * Redirects to /login when no access token is present.
 */
export function RequireAuth({ children }: RequireAuthProps) {
  const router = useRouter();
  const authenticated = useIsAuthenticated();

  useEffect(() => {
    if (!authenticated) {
      router.replace("/login");
    }
  }, [authenticated, router]);

  if (!authenticated) {
    return (
      <div className="dashboard-card p-6 text-sm text-slate-600">
        Checking session…
      </div>
    );
  }

  return <>{children}</>;
}
