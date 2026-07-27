export function CatalogIntro({
  eyebrow = "Maison Atelier Rue",
  title = "Products",
  body = "Parisian business casual pieces curated for weekdays that flow into evening plans.",
}: {
  eyebrow?: string;
  title?: string;
  body?: string;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{eyebrow}</p>
      <h1 className="mt-2 text-3xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-2 max-w-2xl text-sm text-slate-600">{body}</p>
    </div>
  );
}
