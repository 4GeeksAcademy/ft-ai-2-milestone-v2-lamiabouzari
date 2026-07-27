import Link from "next/link";

type HeroProps = {
  eyebrow?: string;
  title: string;
  body: string;
  primaryCta?: { href: string; label: string };
  secondaryCta?: { href: string; label: string };
  featured?: { title: string; body: string; href: string };
};

export function Hero({
  eyebrow = "Spring Campaign",
  title,
  body,
  primaryCta = { href: "/catalog", label: "Shop the campaign" },
  secondaryCta = { href: "/product/veste-de-bureau-marine", label: "Explore lookbook" },
  featured = {
    title: "Le Bureau Doux",
    body: "Unstructured jacket, open-collar shirt, and tapered trousers designed for a soft workday rhythm.",
    href: "/product/veste-de-bureau-marine",
  },
}: HeroProps) {
  return (
    <section className="grid gap-6 rounded-2xl border border-clay/70 bg-white/90 p-6 shadow-sm sm:p-8 lg:grid-cols-[1.25fr_0.75fr] lg:items-end">
      <div>
        <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
          {eyebrow}
        </p>
        <h1 className="mt-4 max-w-xl text-3xl leading-tight text-slate-900 sm:text-4xl md:text-5xl">
          {title}
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-slate-600 sm:text-lg">
          {body}
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          <Link
            href={primaryCta.href}
            className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700"
          >
            {primaryCta.label}
          </Link>
          <Link
            href={secondaryCta.href}
            className="rounded-full border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-slate-500 hover:text-slate-900"
          >
            {secondaryCta.label}
          </Link>
        </div>
      </div>

      <article className="rounded-xl border border-stone/50 bg-oat/70 p-5">
        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
          Featured Set
        </p>
        <h2 className="mt-3 text-2xl text-slate-900">{featured.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-600">
          {featured.body}
        </p>
        <Link
          href={featured.href}
          className="mt-5 inline-block text-sm font-semibold text-slate-800 underline decoration-clay underline-offset-4"
        >
          View featured pieces
        </Link>
      </article>
    </section>
  );
}
