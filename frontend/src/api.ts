import type { Pet, RequestRow, Draft } from "./domain";
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status = 0,
  ) {
    super(message);
  }
}
export class Api {
  token = "";
  private pendingKeys = new Map<string, string>();
  constructor(public base = "http://127.0.0.1:8000/api/v0") {}
  async call<T>(
    path: string,
    method = "GET",
    body?: unknown,
    key?: string,
  ): Promise<T> {
    const operation = JSON.stringify([
      this.base,
      this.token,
      method,
      path,
      body,
    ]);
    const automatic = method !== "GET" && method !== "HEAD" && !key;
    if (automatic) {
      key = this.pendingKeys.get(operation) || crypto.randomUUID();
      this.pendingKeys.set(operation, key);
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const r = await fetch(this.base.replace(/\/$/, "") + path, {
        method,
        signal: controller.signal,
        headers: {
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
          ...(key ? { "Idempotency-Key": key } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (r.status === 204) {
        this.pendingKeys.delete(operation);
        return undefined as T;
      }
      const data = await r.json().catch(() => null);
      if (!r.ok) {
        if (r.status < 500) this.pendingKeys.delete(operation);
        if (r.status === 401) this.token = "";
        throw new ApiError(
          data?.code || "http_error",
          data?.message || `请求失败（${r.status}）`,
          r.status,
        );
      }
      if (data === null)
        throw new ApiError("invalid_response", "服务返回了无效数据");
      this.pendingKeys.delete(operation);
      return data as T;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      throw new ApiError(
        "network_error",
        "连接失败或超时，请检查后端地址和服务；输入仍保留。",
      );
    } finally {
      clearTimeout(timer);
    }
  }
  pets() {
    return this.call<{ items: Pet[]; next_cursor: string | null }>(
      "/pets?limit=100",
    );
  }
  match(id: string, version: number) {
    return this.call(`/requests/${encodeURIComponent(id)}/match`, "POST", {
      expected_version: version,
    });
  }
  book(
    id: string,
    body: {
      expected_version: number;
      helper_id: string;
      scheduled_start: string;
      scheduled_end: string;
      agreed_fee: number;
    },
  ) {
    return this.call(
      `/requests/${encodeURIComponent(id)}/bookings`,
      "POST",
      body,
    );
  }
  bookingAction(
    id: string,
    action: "confirm" | "start" | "submit" | "verify",
    version: number,
  ) {
    return this.call(`/bookings/${encodeURIComponent(id)}/${action}`, "POST", {
      expected_version: version,
    });
  }
  withdrawBooking(id: string, reason: string) {
    return this.call(`/bookings/${encodeURIComponent(id)}/withdraw`, "POST", {
      reason,
    });
  }
  bookingRecords(id: string, cursor?: string) {
    return this.call(
      `/bookings/${encodeURIComponent(id)}/records?limit=100${cursor ? "&cursor=" + encodeURIComponent(cursor) : ""}`,
    );
  }
  addRecord(
    id: string,
    body: {
      checklist_item_id: string;
      kind:
        | "item_completed"
        | "pickup"
        | "departure"
        | "return"
        | "purchase"
        | "delivery";
      occurred_at: string;
      note?: string;
      photo_urls: string[];
      actual_cost?: number;
    },
  ) {
    return this.call(
      `/bookings/${encodeURIComponent(id)}/records`,
      "POST",
      body,
    );
  }
  bookingExceptions(id: string, cursor?: string) {
    return this.call(
      `/bookings/${encodeURIComponent(id)}/exceptions?limit=100${cursor ? "&cursor=" + encodeURIComponent(cursor) : ""}`,
    );
  }
  reportException(
    id: string,
    body: {
      expected_version: number;
      reason_code: string;
      description: string;
      proposed_change?: Record<string, unknown>;
    },
  ) {
    return this.call(
      `/bookings/${encodeURIComponent(id)}/exceptions`,
      "POST",
      body,
    );
  }
  addExceptionNote(id: string, note: string) {
    return this.call(`/exceptions/${encodeURIComponent(id)}/notes`, "POST", {
      note,
    });
  }
  resolveException(
    id: string,
    body: {
      expected_version: number;
      resolution: string;
      decision: "resume" | "end";
      approved_change?: Record<string, unknown>;
    },
  ) {
    return this.call(
      `/exceptions/${encodeURIComponent(id)}/resolve`,
      "POST",
      body,
    );
  }
  requestEvents(id: string, cursor?: string) {
    return this.call(
      `/requests/${encodeURIComponent(id)}/events?limit=100${cursor ? "&cursor=" + encodeURIComponent(cursor) : ""}`,
    );
  }
  requests(scope: string, cursor: string | null) {
    return this.call<{ items: RequestRow[]; next_cursor: string | null }>(
      `/requests?scope=${scope}&limit=20${cursor ? "&cursor=" + encodeURIComponent(cursor) : ""}`,
    );
  }
  create(d: Draft, key: string) {
    return this.call<RequestRow>("/requests", "POST", d, key);
  }
  publish(r: RequestRow, key: string) {
    return this.call<RequestRow>(
      `/requests/${r.id}/publish`,
      "POST",
      { expected_version: r.version },
      key,
    );
  }
}
