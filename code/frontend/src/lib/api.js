import { validateExpense, amount } from "./format.js";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
export function createApi({
  baseUrl,
  getToken,
  fetcher = fetch,
  onUnauthorized = () => {},
}) {
  async function request(path, { method = "GET", body, query, signal } = {}) {
    signal?.throwIfAborted();
    let token;
    try {
      token = await getToken();
    } catch {
      onUnauthorized();
      throw new ApiError(
        "Your session could not be refreshed. Please sign in again.",
        401,
      );
    }
    if (!token) {
      onUnauthorized();
      throw new ApiError(
        "Your session has expired. Please sign in again.",
        401,
      );
    }
    const params = new URLSearchParams(
      Object.entries(query || {}).filter(
        ([, v]) => v !== "" && v !== undefined,
      ),
    );
    const timeout = AbortSignal.timeout(20000);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
    let result;
    try {
      result = await fetcher(
        `${baseUrl}${path}${params.size ? `?${params}` : ""}`,
        {
          method,
          headers: {
            Authorization: `Bearer ${token}`,
            ...(body ? { "Content-Type": "application/json" } : {}),
          },
          body: body ? JSON.stringify(body) : undefined,
          signal: combined,
          credentials: "omit",
          redirect: "error",
        },
      );
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError(
        "Could not reach the service. Check your connection and try again. A submitted change may already have been saved; refresh before repeating it.",
        0,
      );
    }
    let data;
    try {
      data = await result.json();
    } catch {
      throw new ApiError(
        "The service returned an unreadable response. Please refresh.",
        result.status,
      );
    }
    if (!result.ok) {
      if (result.status === 401) onUnauthorized();
      const message =
        result.status === 401
          ? "Your session has expired. Please sign in again."
          : result.status >= 500
            ? "The service is temporarily unavailable. Refresh before repeating a change."
            : data.error || "The request could not be completed.";
      throw new ApiError(message, result.status);
    }
    return data;
  }
  return {
    list: (query, signal) => request("/expenses", { query, signal }),
    detail: (id, signal) =>
      request(`/expenses/${encodeURIComponent(id)}`, { signal }),
    create: (data, signal) =>
      request("/expenses", {
        method: "POST",
        body: validateExpense(data),
        signal,
      }),
    update: (id, data, signal) =>
      request(`/expenses/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: validateExpense(data),
        signal,
      }),
    remove: (id, signal) =>
      request(`/expenses/${encodeURIComponent(id)}`, {
        method: "DELETE",
        signal,
      }),
    stats: (signal) => request("/stats", { query: { months: 6 }, signal }),
    budget: (month, signal) => request("/budget", { query: { month }, signal }),
    saveBudget: (data, signal) =>
      request("/budget", {
        method: "PUT",
        body: {
          ...data,
          monthlyLimit: amount(data.monthlyLimit),
          currency: "AUD",
        },
        signal,
      }),
    uploadPermission: (contentType, signal) =>
      request("/upload-url", { method: "POST", body: { contentType }, signal }),
  };
}

export async function allExpenses(api, query, signal) {
  const items = [];
  let cursor;
  const seen = new Set();
  do {
    signal?.throwIfAborted();
    const page = await api.list({ ...query, limit: 100, cursor }, signal);
    items.push(...page.items);
    cursor = page.nextCursor;
    if (cursor && seen.has(cursor))
      throw new Error("Pagination stopped progressing. Please refresh.");
    seen.add(cursor);
  } while (cursor);
  return items;
}
