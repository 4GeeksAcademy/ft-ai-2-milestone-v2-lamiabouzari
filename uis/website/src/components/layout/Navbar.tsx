import Link from "next/link";

type NavbarProps = {
  cartCount?: number;
};

export function Navbar({ cartCount = 0 }: NavbarProps) {
  return (
    <header className="px-4 pb-3 pt-5 sm:px-8 sm:pt-8">
      <div className="nav-sleeve mx-auto max-w-6xl">
        <nav
          aria-label="Global"
          className="relative overflow-hidden rounded-xl bg-navbase px-4 py-3 text-navtext sm:px-6"
        >
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <Link href="/" className="inline-flex items-baseline gap-2">
              <span className="text-xs uppercase tracking-[0.28em] text-slate-300">
                Maison
              </span>
              <span className="text-lg font-semibold tracking-tight text-navtext">
                Atelier Rue
              </span>
            </Link>

            <form
              className="w-full lg:max-w-xl"
              role="search"
              aria-label="Search products"
              action="/catalog"
              method="get"
            >
              <label htmlFor="site-search" className="sr-only">
                Search
              </label>
              <input
                id="site-search"
                name="q"
                type="search"
                placeholder="Search shirts, blazers, trousers"
                className="w-full rounded-lg border border-slate-500/60 bg-slate-900/30 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-300/70 focus:border-sleeve focus:outline-none focus:ring-2 focus:ring-sleeve/40"
              />
            </form>

            <div className="flex items-center gap-2 self-end lg:self-auto">
              <button
                type="button"
                className="rounded-lg border border-slate-500/70 bg-slate-800/70 px-3 py-2 text-sm font-medium text-slate-100 transition hover:border-sleeve hover:text-white"
              >
                Account
              </button>
              <Link
                href="/cart"
                aria-label="Open bag"
                className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-500/70 bg-slate-800/70 text-slate-100 transition hover:border-sleeve hover:text-white"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  className="h-4 w-4"
                  aria-hidden
                >
                  <path d="M5 8h14l-1 12H6L5 8Z" />
                  <path d="M9 9V7a3 3 0 1 1 6 0v2" />
                </svg>
                {cartCount > 0 ? (
                  <span className="absolute -right-1 -top-1 min-w-[1.1rem] rounded-full bg-rose-500 px-1.5 py-0.5 text-center text-[10px] font-semibold leading-none text-white">
                    {cartCount}
                  </span>
                ) : null}
              </Link>
            </div>
          </div>
        </nav>
      </div>
    </header>
  );
}
