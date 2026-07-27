import type { Product } from "@repo/shared-types";

type ProductGalleryProps = {
  product: Product;
};

export function ProductGallery({ product }: ProductGalleryProps) {
  return (
    <div className="rounded-xl bg-slate-50 p-5 lg:h-[640px]">
      {product.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={product.image}
          alt={product.imageAlt ?? product.name}
          className="h-full min-h-[360px] w-full rounded-lg object-cover"
        />
      ) : (
        <div className="placeholder-block h-full min-h-[360px] rounded-lg" />
      )}
    </div>
  );
}
