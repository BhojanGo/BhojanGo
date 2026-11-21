export interface ReorderResponse {
  restaurant: { id: string; slug?: string; name: string; currency?: string };
  items: { menu_item_id: string; name: string; quantity: number; options?: { group: string; option: string; name?: string | null }[];
    price: number | string; available?: boolean | null }[];
  unavailable?: string[];
  problems?: { item: string; reason: string; option?: string | null; detail?: string | null }[];
}
export interface ReorderLine {
  menuItemId: string; name: string; unitPrice: number; quantity: number; picks: { group: string; option: string }[]; summary: string;
}
export interface ReorderNote { key: string; values: Record<string, string> }
export declare const PROBLEMS: string[];
export declare function reorderToBag<R extends ReorderResponse>(r: R, prefix?: string): {
  restaurant: R["restaurant"]; lines: ReorderLine[]; notes: ReorderNote[];
};
