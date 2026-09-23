"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout, useIsAuthenticated } from "@/lib/auth";

interface BackofficeShellProps {
  readonly children: React.ReactNode;
}

const NAV_LINKS = [
  { href: "/products", label: "Products" },
  { href: "/orders/inbound", label: "Inbound Orders" },
  { href: "/orders/outbound", label: "Outbound Orders" },
  { href: "/orders", label: "Order History" },
  { href: "/reporting", label: "Reporting" },
  { href: "/incidents", label: "Incident Analysis" },
];

export function BackofficeShell({ children }: BackofficeShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const authenticated = useIsAuthenticated();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <div className="backoffice-grid min-h-screen">
      <header className="border-b border-line bg-panel/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 sm:px-8 lg:px-10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-strong">
                Internal Operations
              </p>
              <h1 className="font-display text-2xl text-foreground">
                Maison Atelier Rue Backoffice
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent-strong">
                Milestone 5
              </div>
              {authenticated ? (
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-full border border-line px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-panel-soft"
                >
                  Log out
                </button>
              ) : null}
            </div>
          </div>
          <nav className="flex flex-wrap gap-2">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? "bg-accent text-white"
                      : "bg-panel-soft text-slate-700 hover:bg-accent-soft"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-8 lg:px-10">
        {children}
      </main>
    </div>
  );
}
