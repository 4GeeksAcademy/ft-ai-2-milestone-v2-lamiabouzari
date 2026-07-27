"use client";

import { useState } from "react";
import { SITE_CONTACT, formatPrice, type Product } from "@repo/shared-types";

type ProductInfoProps = {
  product: Product;
  onAddToCart?: (payload: { size: string; quantity: number }) => void;
};

export function ProductInfo({ product, onAddToCart }: ProductInfoProps) {
  const [size, setSize] = useState(product.displaySize);
  const [quantity, setQuantity] = useState(1);

  return (
    <div className="flex flex-col lg:h-[640px]">
      <p className="text-sm font-medium uppercase tracking-[0.16em] text-slate-500">
        {SITE_CONTACT.brandName}
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
        {product.name}
      </h1>

      <div className="mt-4 border-b border-slate-200 pb-4">
        <p className="text-2xl font-semibold italic text-slate-500">
          {formatPrice(product.price, product.currency)}
        </p>
      </div>

      <p className="mt-6 text-base italic text-slate-600">
        {product.shortDescription}
      </p>

      <dl className="mt-6 space-y-3 text-sm text-slate-700">
        <div className="flex items-center justify-between border-b border-slate-200 pb-2">
          <dt className="font-medium text-slate-500">Product code</dt>
          <dd className="font-semibold">{product.code}</dd>
        </div>
        <div className="border-b border-slate-200 pb-3">
          <dt className="font-medium text-slate-500">Size</dt>
          <dd className="mt-2">
            <div
              className="flex flex-wrap gap-2"
              role="radiogroup"
              aria-label="Select size"
            >
              {product.sizes.map((option) => (
                <label key={option} className="cursor-pointer">
                  <input
                    type="radio"
                    name={`size-${product.id}`}
                    value={option}
                    checked={size === option}
                    onChange={() => setSize(option)}
                    className="peer sr-only"
                  />
                  <span className="inline-block rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-slate-700 transition hover:border-slate-900 peer-checked:border-slate-900 peer-checked:bg-slate-500 peer-checked:text-white">
                    {option}
                  </span>
                </label>
              ))}
            </div>
          </dd>
        </div>
      </dl>

      <div className="mt-7 flex w-full flex-col items-stretch gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-center">
        <div className="flex items-center justify-center gap-2">
          <label htmlFor="quantity" className="text-sm font-medium text-slate-500">
            Quantity:
          </label>
          <input
            id="quantity"
            name="quantity"
            type="number"
            min={1}
            max={10}
            value={quantity}
            onChange={(event) =>
              setQuantity(Math.max(1, Number(event.target.value) || 1))
            }
            className="h-11 w-14 rounded-lg border border-slate-300 bg-white px-3 text-center text-sm font-semibold text-slate-900 focus:border-navbase focus:outline-none focus:ring-2 focus:ring-navbase/20"
          />
        </div>
        <button
          type="button"
          onClick={() => onAddToCart?.({ size, quantity })}
          className="h-11 w-full rounded-lg border border-slate-300 px-6 text-sm font-semibold uppercase tracking-[0.12em] text-slate-900 transition hover:bg-slate-500 hover:text-white sm:w-auto sm:flex-1"
        >
          Add to cart
        </button>
      </div>
    </div>
  );
}
