interface BackofficeShellProps {
  readonly children: React.ReactNode;
}

export function BackofficeShell({ children }: BackofficeShellProps) {
  return (
    <div className="backoffice-grid min-h-screen">
      <header className="border-b border-line bg-panel/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-8 lg:px-10">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-strong">
              Internal Operations
            </p>
            <h1 className="font-display text-2xl text-foreground">
              Maison Atelier Rue Backoffice
            </h1>
          </div>
          <div className="rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent-strong">
            Milestone 4
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-8 lg:px-10">
        {children}
      </main>
    </div>
  );
}
