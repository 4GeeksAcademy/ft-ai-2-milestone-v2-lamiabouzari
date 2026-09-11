import { apiRequest } from "@/lib/api-client";

export type Warehouse = "LA" | "ZGZ";
export type Category = "fashion" | "electronics" | "cosmetics";
export type ExitType = "dispatch" | "loss";

export const WAREHOUSES: Warehouse[] = ["LA", "ZGZ"];
export const CATEGORIES: Category[] = ["fashion", "electronics", "cosmetics"];
export const EXIT_TYPES: ExitType[] = ["dispatch", "loss"];

export interface Product {
  id: number;
  name: string;
  sku: string;
  client_name: string;
  category: Category;
  warehouse: Warehouse;
  current_stock: number;
}

export interface ProductCreateInput {
  name: string;
  sku: string;
  client_name: string;
  category: Category;
  warehouse: Warehouse;
}

export interface StockEntry {
  id: number;
  sku_id: number;
  quantity: number;
  reference: string;
  warehouse: Warehouse;
  created_at: string;
  user_uuid: string;
}

export interface InboundOrderInput {
  sku_id: number;
  quantity: number;
  reference: string;
  warehouse: Warehouse;
}

export interface StockExit {
  id: number;
  sku_id: number;
  quantity: number;
  exit_type: ExitType;
  tracking_number: string | null;
  warehouse: Warehouse;
  created_at: string;
  user_uuid: string;
}

export interface OutboundOrderInput {
  sku_id: number;
  quantity: number;
  exit_type: ExitType;
  tracking_number?: string | null;
  warehouse: Warehouse;
}

export interface Order {
  movement_type: "inbound" | "outbound";
  id: number;
  sku_id: number;
  sku: string;
  name: string;
  client_name: string;
  warehouse: Warehouse;
  quantity: number;
  created_at: string;
  user_uuid: string;
  reference: string | null;
  exit_type: ExitType | null;
  tracking_number: string | null;
}

export function listProducts(): Promise<Product[]> {
  return apiRequest<Product[]>("/inventory/products");
}

export function createProduct(input: ProductCreateInput): Promise<Product> {
  return apiRequest<Product>("/inventory/products", {
    method: "POST",
    body: input,
    auth: true,
  });
}

export function createInboundOrder(input: InboundOrderInput): Promise<StockEntry> {
  return apiRequest<StockEntry>("/inventory/orders/inbound", {
    method: "POST",
    body: input,
    auth: true,
  });
}

export function createOutboundOrder(input: OutboundOrderInput): Promise<StockExit> {
  return apiRequest<StockExit>("/inventory/orders/outbound", {
    method: "POST",
    body: input,
    auth: true,
  });
}

export function listOrders(): Promise<Order[]> {
  return apiRequest<Order[]>("/inventory/orders");
}
