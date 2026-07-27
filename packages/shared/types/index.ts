/**
 * Maison Atelier Rue — shared retail types.
 * Bound by memory-bank/specs/decisions.md (EUR, category taxonomy, identity).
 */

export type Id = string;

export type CurrencyCode = "EUR";

/** SPEC / footer taxonomy (D6). */
export type ProductCategory =
  | "footwear"
  | "shirts"
  | "pants"
  | "accessories";

export type ProductListTag = "new-arrival" | "best-seller";

export const PRODUCT_CATEGORIES: readonly ProductCategory[] = [
  "footwear",
  "shirts",
  "pants",
  "accessories",
] as const;

/** Catalog filter sizes (D7), excluding "all". */
export const CATALOG_SIZE_FILTERS: readonly string[] = [
  "xs",
  "s",
  "m",
  "l",
  "xl",
  "38",
  "40",
  "42",
  "44",
  "one-size",
] as const;

/** Mock cart tax rate (D4) — simplification, not legal advice. */
export const CART_TAX_RATE = 0.1;

export interface BaseEntity {
  id: Id;
  createdAt?: string;
  updatedAt?: string;
}

export interface Product extends BaseEntity {
  slug: string;
  code: string;
  name: string;
  shortDescription: string;
  price: number;
  currency: CurrencyCode;
  category: ProductCategory;
  /** Display eyebrow, e.g. "Men's Shirt" — not a filter id. */
  categoryLabel: string;
  /** Available sizes for PDP / filters. */
  sizes: string[];
  /** Representative size shown on catalog badges. */
  displaySize: string;
  image?: string;
  imageAlt?: string;
  details?: string[];
  materials?: string[];
  stylingSuggestions?: string;
  listTags?: ProductListTag[];
}

export interface CartLine {
  id: Id;
  productId: Id;
  name: string;
  code: string;
  image: string;
  imageAlt?: string;
  unitPrice: number;
  currency: CurrencyCode;
  quantity: number;
  size?: string;
}

export interface CartTotals {
  subtotal: number;
  tax: number;
  total: number;
  currency: CurrencyCode;
  taxRate: number;
}

export interface CheckoutPersonalDetails {
  firstName: string;
  lastName: string;
  email: string;
  phone?: string;
}

export interface CheckoutShippingAddress {
  street: string;
  unit?: string;
  postalCode: string;
  city: string;
  country: string;
}

export interface CheckoutPaymentDetails {
  cardName: string;
  cardNumber: string;
  expiry: string;
  cvc: string;
}

/** Canonical site contact (D5). */
export interface SiteContact {
  brandName: string;
  email: string;
  phone: string;
  address: string;
  url: string;
}

export const SITE_CONTACT: SiteContact = {
  brandName: "Maison Atelier Rue",
  email: "bonjour@maisonatelierrue.example",
  phone: "+33 1 00 45 67 89",
  address: "14 Rue de la Tranquillité, Paris",
  url: "https://maisonatelierrue.example",
};

export const FOOTER_CATEGORIES: readonly {
  category: ProductCategory;
  label: string;
}[] = [
  { category: "footwear", label: "Footwear" },
  { category: "shirts", label: "Shirts" },
  { category: "pants", label: "Pants" },
  { category: "accessories", label: "Accessories" },
] as const;

/** Format price for UI (D3): "EUR 245" or "EUR 79.00" when cents matter. */
export function formatPrice(amount: number, currency: CurrencyCode = "EUR"): string {
  const hasCents = !Number.isInteger(amount);
  const formatted = hasCents ? amount.toFixed(2) : String(amount);
  return `${currency} ${formatted}`;
}

export function computeCartTotals(
  lines: readonly CartLine[],
  taxRate: number = CART_TAX_RATE
): CartTotals {
  const currency: CurrencyCode = lines[0]?.currency ?? "EUR";
  const subtotal = lines.reduce(
    (sum, line) => sum + line.unitPrice * line.quantity,
    0
  );
  const tax = Math.round(subtotal * taxRate * 100) / 100;
  const total = Math.round((subtotal + tax) * 100) / 100;
  return { subtotal, tax, total, currency, taxRate };
}
