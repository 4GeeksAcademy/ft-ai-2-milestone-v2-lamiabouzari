import type { CartLine, Product } from "@repo/shared-types";

/**
 * Mock catalog for Maison Atelier Rue migration (Phase 2).
 * Content drawn from website_v1; categories/currency follow specs/decisions.md.
 */

export const products: Product[] = [
  {
    id: "prod_rive-left-bank-blazer",
    slug: "rive-left-bank-blazer",
    code: "AR-BZ-1001",
    name: "Rive Left-Bank Blazer",
    shortDescription: "Light wool twill in greige",
    price: 245,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Blazer",
    sizes: ["xs", "s", "m", "l", "xl"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1617127365659-c47fa864d8bc?auto=format&fit=crop&w=1200&q=80",
    imageAlt: "Greige tailored wool blazer",
    listTags: ["new-arrival"],
  },
  {
    id: "prod_montparnasse-poplin-shirt",
    slug: "montparnasse-poplin-shirt",
    code: "AR-SH-1002",
    name: "Montparnasse Poplin Shirt",
    shortDescription: "Relaxed spread collar",
    price: 95,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Men's Shirt",
    sizes: ["s", "m", "l", "xl"],
    displaySize: "m",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/6/6d/Dress_Wear_styles_Bangladesh_-_Mens_poplin_shirts.jpg",
    imageAlt: "Men's poplin shirt assortment",
    listTags: ["new-arrival"],
  },
  {
    id: "prod_tuileries-relaxed-trousers",
    slug: "tuileries-relaxed-trousers",
    code: "AR-TR-1003",
    name: "Tuileries Relaxed Trousers",
    shortDescription: "Soft pleat, fluid drape",
    price: 128,
    currency: "EUR",
    category: "pants",
    categoryLabel: "Pants",
    sizes: ["xs", "s", "m", "l", "xl"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Relaxed pleated trousers",
    listTags: ["new-arrival"],
  },
  {
    id: "prod_canal-leather-loafers",
    slug: "canal-leather-loafers",
    code: "AR-FW-1004",
    name: "Canal Leather Loafers",
    shortDescription: "Brushed calfskin finish",
    price: 198,
    currency: "EUR",
    category: "footwear",
    categoryLabel: "Footwear",
    sizes: ["38", "40", "42", "44"],
    displaySize: "42",
    image:
      "https://images.unsplash.com/photo-1490114538077-0a7f8cb49891?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Brown leather loafers",
    listTags: ["new-arrival"],
  },
  {
    id: "prod_saint-germain-utility-jacket",
    slug: "saint-germain-utility-jacket",
    code: "AR-BZ-2001",
    name: "Saint-Germain Utility Jacket",
    shortDescription: "Cotton-linen blend",
    price: 174,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Jacket",
    sizes: ["s", "m", "l", "xl"],
    displaySize: "m",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/3/30/Utility_Shirt_Jacket.jpg",
    imageAlt: "Utility shirt jacket in cotton blend",
    listTags: ["best-seller"],
  },
  {
    id: "prod_rue-cler-oxford-shirt",
    slug: "rue-cler-oxford-shirt",
    code: "AR-SH-2002",
    name: "Rue Cler Oxford Shirt",
    shortDescription: "Clean button-down line",
    price: 88,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Men's Shirt",
    sizes: ["s", "m", "l"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Blue oxford button-down shirt",
    listTags: ["best-seller"],
  },
  {
    id: "prod_passy-pleated-pants",
    slug: "passy-pleated-pants",
    code: "AR-TR-2003",
    name: "Passy Pleated Pants",
    shortDescription: "Mid-rise, ankle crop",
    price: 120,
    currency: "EUR",
    category: "pants",
    categoryLabel: "Pants",
    sizes: ["xs", "s", "m", "l"],
    displaySize: "s",
    image:
      "https://images.unsplash.com/photo-1521577352947-9bb58764b69a?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Pleated pants with tapered silhouette",
    listTags: ["best-seller"],
  },
  {
    id: "prod_marais-weekender-tote",
    slug: "marais-weekender-tote",
    code: "AR-AC-2004",
    name: "Marais Weekender Tote",
    shortDescription: "Water-resistant canvas",
    price: 112,
    currency: "EUR",
    category: "accessories",
    categoryLabel: "Accessory",
    sizes: ["one-size"],
    displaySize: "one-size",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/c/c1/Canvas_two-tone_tote_Navy_and_Natural7_%289038437258%29.jpg",
    imageAlt: "Two-tone canvas weekender tote",
    listTags: ["best-seller"],
  },
  {
    id: "prod_veste-de-bureau-marine",
    slug: "veste-de-bureau-marine",
    code: "AR-FB-2407",
    name: "Veste de Bureau - Marine",
    shortDescription:
      "Designed with a soft shoulder and easy drape for polished weekdays that still feel relaxed.",
    price: 189,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Blazer",
    sizes: ["xxs", "xs", "s", "m", "l", "xl", "xxl"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1617127365659-c47fa864d8bc?auto=format&fit=crop&w=1200&q=80",
    imageAlt: "Model wearing a navy wool blazer",
    details: [
      "Soft-shoulder silhouette",
      "Regular fit through chest and waist",
      "Two-button closure",
      "Double back vent",
    ],
    materials: [
      "Shell: 58% wool, 38% cotton, 4% elastane",
      "Lining: 100% recycled viscose",
      "Wash at or below 30°C",
    ],
    stylingSuggestions:
      "Tailored to move seamlessly through your week. Dress it up for crucial client presentations with a white Oxford and loafers, dress it down for creative office days with a knit polo and chinos, or take it to after-work drinks over dark denim. When travel calls, it packs effortlessly alongside your go-to wrinkle-resistant trousers.",
    listTags: ["best-seller"],
  },
  {
    id: "prod_bastille-chambray",
    slug: "bastille-chambray",
    code: "AR-SH-1010",
    name: "Bastille Chambray",
    shortDescription: "A lightweight chambray with subtle matte buttons.",
    price: 84,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Men's Shirt",
    sizes: ["s", "m", "l"],
    displaySize: "s",
    image:
      "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Chambray shirt with matte buttons",
  },
  {
    id: "prod_belleville-silk-blouse",
    slug: "belleville-silk-blouse",
    code: "AR-SH-1011",
    name: "Belleville Silk Blouse",
    shortDescription: "Fluid silk with understated drape and sheen.",
    price: 105,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Women's Shirt",
    sizes: ["xs", "s", "m", "l"],
    displaySize: "xs",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/3/31/1965_Chanel_suit_and_silk_blouse_detail.jpg",
    imageAlt: "Silk blouse with fluid drape",
  },
  {
    id: "prod_louvre-linen-shirt",
    slug: "louvre-linen-shirt",
    code: "AR-SH-1012",
    name: "Louvre Linen Shirt",
    shortDescription: "Breathable flax blend in warm sandstone tone.",
    price: 95,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Men's Shirt",
    sizes: ["m", "l", "xl"],
    displaySize: "xl",
    image:
      "https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Linen shirt in warm neutral tone",
  },
  {
    id: "prod_chino-sable",
    slug: "pantalon-chino-sable",
    code: "AR-TR-224",
    name: "Pantalon Chino Sable",
    shortDescription: "Sand chino trousers with an easy taper.",
    price: 95,
    currency: "EUR",
    category: "pants",
    categoryLabel: "Pants",
    sizes: ["s", "m", "l", "xl"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Sand chino trousers",
  },
  {
    id: "prod_pleated-trousers-ardoise",
    slug: "pleated-trousers-ardoise",
    code: "AR-TR-2010",
    name: "Pleated Trousers Ardoise",
    shortDescription: "Slate pleated trousers for soft office rhythm.",
    price: 138,
    currency: "EUR",
    category: "pants",
    categoryLabel: "Pants",
    sizes: ["s", "m", "l"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Slate pleated trousers",
  },
  {
    id: "prod_relaxed-cotton-trousers",
    slug: "relaxed-cotton-trousers",
    code: "REF-TR-1880",
    name: "Relaxed Cotton Trousers",
    shortDescription: "Easy cotton trousers with a quiet taper.",
    price: 62.5,
    currency: "EUR",
    category: "pants",
    categoryLabel: "Pants",
    sizes: ["s", "m", "l", "xl"],
    displaySize: "l",
    image:
      "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Relaxed cotton trousers",
  },
  {
    id: "prod_rivoli-leather-loafer",
    slug: "rivoli-leather-loafer",
    code: "AR-FW-3010",
    name: "Rivoli Leather Loafer",
    shortDescription: "Brushed leather loafer in espresso brown.",
    price: 138,
    currency: "EUR",
    category: "footwear",
    categoryLabel: "Footwear",
    sizes: ["38", "40", "42", "44"],
    displaySize: "40",
    image:
      "https://images.unsplash.com/photo-1490114538077-0a7f8cb49891?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Espresso brown leather loafers",
  },
  {
    id: "prod_concorde-derby",
    slug: "concorde-derby",
    code: "AR-FW-3011",
    name: "Concorde Derby",
    shortDescription: "Derby with a slim profile and matte sole.",
    price: 146,
    currency: "EUR",
    category: "footwear",
    categoryLabel: "Footwear",
    sizes: ["40", "42", "44"],
    displaySize: "42",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/f/f0/Shoe-Blucher-Black_with_rubber_sole.jpg",
    imageAlt: "Black leather derby shoe",
  },
  {
    id: "prod_derbies-cuir-noir",
    slug: "derbies-cuir-noir",
    code: "AR-SH-412",
    name: "Derbies Cuir Noir",
    shortDescription: "Black leather derby shoes for evening polish.",
    price: 149,
    currency: "EUR",
    category: "footwear",
    categoryLabel: "Footwear",
    sizes: ["40", "42", "44"],
    displaySize: "42",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/9/92/Leather_shoes_4_man.JPG",
    imageAlt: "Pair of black leather derby shoes",
  },
  {
    id: "prod_tuileries-handbag",
    slug: "tuileries-handbag",
    code: "AR-AC-4010",
    name: "Tuileries Handbag",
    shortDescription: "Structured pebble-leather handbag in almond tan.",
    price: 168,
    currency: "EUR",
    category: "accessories",
    categoryLabel: "Accessory",
    sizes: ["one-size"],
    displaySize: "one-size",
    image:
      "https://cdn.dummyjson.com/product-images/womens-bags/heshe-women's-leather-bag/thumbnail.webp",
    imageAlt: "Structured tan leather handbag",
  },
  {
    id: "prod_passy-silk-necktie",
    slug: "passy-silk-necktie",
    code: "AR-AC-4011",
    name: "Passy Silk Necktie",
    shortDescription: "Navy silk tie with discreet geometric motif.",
    price: 54,
    currency: "EUR",
    category: "accessories",
    categoryLabel: "Accessory",
    sizes: ["one-size"],
    displaySize: "one-size",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/2/2f/L85HS09_blake_vincent_blue_striped_silk_necktie_2.jpg",
    imageAlt: "Navy silk necktie with subtle stripe motif",
  },
  {
    id: "prod_textured-linen-overshirt",
    slug: "textured-linen-overshirt",
    code: "REF-LN-2104",
    name: "Textured Linen Overshirt",
    shortDescription: "Layerable linen overshirt for mild city weather.",
    price: 79,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Shirt",
    sizes: ["s", "m", "l", "xl"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Textured linen overshirt",
  },
  {
    id: "prod_tailored-midnight-blazer",
    slug: "tailored-midnight-blazer",
    code: "REF-BZ-3022",
    name: "Tailored Midnight Blazer with Contrast Stitching",
    shortDescription: "Midnight blazer with quiet contrast stitching.",
    price: 149,
    currency: "EUR",
    category: "shirts",
    categoryLabel: "Blazer",
    sizes: ["s", "m", "l", "xl"],
    displaySize: "m",
    image:
      "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=900&q=80",
    imageAlt: "Tailored midnight blazer",
  },
];

export const catalogProducts: Product[] = products.slice(0, 20);

export function getProductBySlug(slug: string): Product | undefined {
  return products.find((product) => product.slug === slug);
}

export function getProductById(id: string): Product | undefined {
  return products.find((product) => product.id === id);
}

export function getProductsByTag(
  tag: NonNullable<Product["listTags"]>[number]
): Product[] {
  return products.filter((product) => product.listTags?.includes(tag));
}

export const newArrivals = getProductsByTag("new-arrival");
export const bestSellers = getProductsByTag("best-seller");

/** Featured PDP for Phase 5 product view. */
export const featuredProduct =
  getProductBySlug("veste-de-bureau-marine") ?? products[0];

/** Three sample cart lines (SPEC + cart.html). */
export const sampleCartLines: CartLine[] = [
  {
    id: "line_1",
    productId: "prod_textured-linen-overshirt",
    name: "Textured Linen Overshirt",
    code: "REF-LN-2104",
    image:
      "https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=120&q=80",
    imageAlt: "Textured linen overshirt",
    unitPrice: 79,
    currency: "EUR",
    quantity: 2,
    size: "m",
  },
  {
    id: "line_2",
    productId: "prod_tailored-midnight-blazer",
    name: "Tailored Midnight Blazer with Contrast Stitching",
    code: "REF-BZ-3022",
    image:
      "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=120&q=80",
    imageAlt: "Tailored midnight blazer",
    unitPrice: 149,
    currency: "EUR",
    quantity: 1,
    size: "m",
  },
  {
    id: "line_3",
    productId: "prod_relaxed-cotton-trousers",
    name: "Relaxed Cotton Trousers",
    code: "REF-TR-1880",
    image:
      "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=120&q=80",
    imageAlt: "Relaxed cotton trousers",
    unitPrice: 62.5,
    currency: "EUR",
    quantity: 3,
    size: "l",
  },
];
