import Link from "next/link";
import { formatPrice, type Product } from "@repo/shared-types";

type ProductCardProps = {
  product: Product;
  variant?: "rail" | "catalog" | "compact";
};

export function ProductCard({
  product,
  variant = "rail",
}: ProductCardProps) {
  const href = `/product/${product.slug}`;
  const price = formatPrice(product.price, product.currency);

  if (variant === "catalog") {
    return (
      <Link
        href={href}
        className="product-card block h-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
      >
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
          {product.categoryLabel}
        </p>
        <div className="placeholder-block mt-3 h-36 rounded-lg">
          {product.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={product.image}
              alt={product.imageAlt ?? product.name}
              className="h-full w-full rounded-lg object-cover"
            />
          ) : null}
        </div>
        <h3 className="mt-3 text-base font-semibold text-slate-900">
          {product.name}
        </h3>
        <p className="mt-1 text-sm text-slate-600">{product.shortDescription}</p>
        <div className="mt-4 flex items-center justify-between text-sm">
          <span className="font-medium text-slate-800">{price}</span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium uppercase text-slate-600">
            {product.displaySize === "one-size" ? "One Size" : product.displaySize}
          </span>
        </div>
      </Link>
    );
  }

  if (variant === "compact") {
    return (
      <Link
        href={href}
        className="block rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition hover:border-slate-300"
      >
        <div className="placeholder-block h-44 rounded-lg">
          {product.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={product.image}
              alt={product.imageAlt ?? product.name}
              className="h-full w-full rounded-lg object-cover"
            />
          ) : null}
        </div>
        <h3 className="mt-3 text-sm font-semibold text-slate-900">{product.name}</h3>
        <p className="mt-1 text-xs text-slate-500">Code {product.code}</p>
        <p className="mt-2 text-sm font-semibold text-slate-900">{price}</p>
      </Link>
    );
  }

  return (
    <Link
      href={href}
      className="block rounded-xl border border-clay/60 bg-white p-4 transition hover:border-clay"
    >
      <div className="placeholder-block h-44 rounded-lg">
        {product.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image}
            alt={product.imageAlt ?? product.name}
            className="h-full w-full rounded-lg object-cover"
          />
        ) : null}
      </div>
      <h3 className="mt-4 text-lg text-slate-900">{product.name}</h3>
      <p className="mt-1 text-sm text-slate-600">{product.shortDescription}</p>
      <p className="mt-3 text-sm font-semibold text-slate-800">{price}</p>
    </Link>
  );
}
