export declare const STATUS_STEPS: string[];
export declare function statusStep(status: string | null | undefined): number;
export declare function shownStatus(orderStatus: string | null | undefined, liveStatus: string | null | undefined): string;
export declare function nextLiveStatus(current: string | null | undefined, incoming: string | null | undefined): string | null;
