import {
  amount,
  cents,
  currentMonth,
  sydneyDay,
  validateExpense,
} from "./format.js";
import { delay } from "./upload.js";

export const DEMO_KEY = "smart-expense-demo-v1";
function seed() {
  const month = currentMonth();
  const shops = [
    ["Coles", "Groceries", "84.60"],
    ["Woolworths", "Groceries", "112.35"],
    ["The Grounds Café", "Dining", "24.50"],
    ["Opal top-up", "Transport", "50.00"],
    ["ALDI", "Groceries", "65.90"],
    ["JB Hi-Fi", "Shopping", "129.00"],
    ["Chemist Warehouse", "Health", "32.40"],
    ["Shell", "Transport", "78.20"],
    ["Little Italy", "Dining", "58.00"],
    ["Bunnings", "Shopping", "45.75"],
    ["Coles", "Groceries", "42.80"],
    ["Morning coffee", "Dining", "5.50"],
    ["Woolworths", "Groceries", "93.65"],
    ["Opal top-up", "Transport", "30.00"],
  ];
  const expenses = shops.map(([merchant, category, total], i) => ({
    expenseId: crypto.randomUUID(),
    merchant,
    category,
    total,
    receiptDate: `${month}-${String(Math.max(1, Number(sydneyDay().slice(-2)) - (i % 8))).padStart(2, "0")}`,
    currency: "AUD",
    source: i % 3 ? "manual" : "receipt",
    status: "PROCESSED",
    createdAt: new Date().toISOString(),
  }));
  const [year, m] = month.split("-").map(Number);
  for (let i = 1; i <= 5; i++) {
    const index = year * 12 + m - 1 - i;
    expenses.push({
      expenseId: crypto.randomUUID(),
      merchant: "Previous month sample",
      category: "Other",
      total: String([1120, 960, 1340, 890, 1080][i - 1]),
      receiptDate: `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}-12`,
      currency: "AUD",
      source: "manual",
      status: "PROCESSED",
      createdAt: new Date().toISOString(),
    });
  }
  return {
    expenses,
    budgets: { [month]: "1500.00" },
    weeklySummary: false,
    email: "",
  };
}

export function createDemoApi(storage = localStorage) {
  if (!import.meta.env.DEV)
    throw new Error("Demo storage is unavailable in production.");
  let data;
  try {
    data = JSON.parse(storage.getItem(DEMO_KEY) || "null");
  } catch {
    throw new Error(
      "Demo storage is unreadable. Clear this site’s demo data to start again.",
    );
  }
  if (!data) {
    data = seed();
    storage.setItem(DEMO_KEY, JSON.stringify(data));
  }
  if (!Array.isArray(data.expenses) || !data.budgets)
    throw new Error(
      "Demo storage is incompatible. Clear this site’s demo data to start again.",
    );
  const save = () => storage.setItem(DEMO_KEY, JSON.stringify(data));
  const copy = (value) => structuredClone(value);
  const check = (signal) => signal?.throwIfAborted();
  function find(id) {
    const item = data.expenses.find((e) => e.expenseId === id);
    if (!item) throw new Error("Expense not found.");
    return item;
  }
  function spent(month) {
    return data.expenses
      .filter(
        (e) => e.status === "PROCESSED" && e.receiptDate?.startsWith(month),
      )
      .reduce((sum, e) => sum + cents(e.total), 0);
  }
  function budget(month) {
    const limit = cents(data.budgets[month] || 0),
      total = spent(month);
    return {
      month,
      monthlyLimit: limit / 100,
      spent: total / 100,
      remaining: (limit - total) / 100,
      utilisation: limit ? (total / limit) * 100 : null,
      currency: "AUD",
      weeklySummary: data.weeklySummary,
      email: data.email,
      subscriptionStatus: data.email ? "pending_or_blocked" : "not_subscribed",
      notificationState: "not_sent",
    };
  }
  const api = {
    async list(query = {}, signal) {
      check(signal);
      // Filter AFTER a bounded evaluated page, matching the backend's empty-page contract.
      const start = Number(query.cursor || 0),
        limit = Number(query.limit || 25);
      const raw = data.expenses.slice(start, start + limit);
      const items = raw.filter(
        (e) =>
          (!query.month || e.receiptDate?.startsWith(query.month)) &&
          (!query.category || e.category === query.category) &&
          (!query.from || e.receiptDate >= query.from) &&
          (!query.to || e.receiptDate <= query.to),
      );
      return copy({
        items,
        ...(start + limit < data.expenses.length
          ? { nextCursor: String(start + limit) }
          : {}),
      });
    },
    async detail(id, signal) {
      check(signal);
      const item = find(id);
      if (item.demoReadyAt && Date.now() >= item.demoReadyAt) {
        if (item.demoOutcome === "failure")
          Object.assign(item, {
            status: "FAILED",
            errorMessage:
              "Simulated extraction failure: no readable total. No AWS service was called.",
            retryable: false,
          });
        else
          Object.assign(item, {
            status: "PROCESSED",
            merchant: "Demo receipt · simulated",
            receiptDate: sydneyDay(),
            total: "28.70",
            category: "Groceries",
            currency: "AUD",
            currencySource: "application_default",
          });
        delete item.demoReadyAt;
        delete item.demoOutcome;
        save();
      }
      return copy(item);
    },
    async create(input, signal) {
      check(signal);
      const item = {
        ...validateExpense(input),
        expenseId: crypto.randomUUID(),
        source: "manual",
        status: "PROCESSED",
        createdAt: new Date().toISOString(),
      };
      data.expenses.unshift(item);
      save();
      return copy(item);
    },
    async update(id, input, signal) {
      check(signal);
      const item = find(id);
      if (item.status !== "PROCESSED")
        throw new Error("Only completed expenses can be edited.");
      Object.assign(item, validateExpense(input));
      save();
      return copy(item);
    },
    async remove(id, signal) {
      check(signal);
      find(id);
      data.expenses = data.expenses.filter((e) => e.expenseId !== id);
      save();
      return { deleted: true };
    },
    async stats(signal) {
      check(signal);
      const month = currentMonth(),
        [y, m] = month.split("-").map(Number),
        byMonth = {},
        byCategory = {};
      for (let i = 5; i >= 0; i--) {
        const index = y * 12 + m - 1 - i;
        const period = `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
        byMonth[period] = spent(period) / 100;
      }
      const current = data.expenses.filter(
        (e) => e.status === "PROCESSED" && e.receiptDate?.startsWith(month),
      );
      for (const e of current)
        byCategory[e.category] = (byCategory[e.category] || 0) + cents(e.total);
      Object.keys(byCategory).forEach((key) => {
        byCategory[key] /= 100;
      });
      const b = budget(month);
      return {
        byMonth,
        byCategory,
        thisMonth: {
          total: b.spent,
          budget: b.monthlyLimit,
          remaining: b.remaining,
          count: current.length,
          currency: "AUD",
        },
      };
    },
    async budget(month, signal) {
      check(signal);
      return budget(month);
    },
    async saveBudget(input, signal) {
      check(signal);
      data.budgets[input.month] = amount(input.monthlyLimit);
      if (input.email) data.email = input.email;
      if (input.weeklySummary !== undefined)
        data.weeklySummary = input.weeklySummary;
      save();
      return budget(input.month);
    },
    async uploadPermission(_contentType, signal) {
      check(signal);
      const item = {
        expenseId: crypto.randomUUID(),
        source: "receipt",
        status: "PENDING",
        createdAt: new Date().toISOString(),
      };
      data.expenses.unshift(item);
      save();
      return {
        expenseId: item.expenseId,
        expiresIn: 300,
        upload: { url: "DEMO_NO_NETWORK", fields: {} },
      };
    },
    async simulateUpload(
      permission,
      _file,
      { signal, onProgress, outcome = "success" },
    ) {
      for (const percent of [15, 45, 80, 100]) {
        await delay(150, signal);
        onProgress(percent);
      }
      Object.assign(find(permission.expenseId), {
        status: "PROCESSING",
        demoReadyAt: Date.now() + 1500,
        demoOutcome: outcome,
      });
      save();
    },
  };
  return api;
}

export function createDemoAuth() {
  let user = {
    email: "demo@example.com",
    emailVerified: true,
    name: "Demo member",
  };
  const listeners = new Set();
  return {
    async session() {
      return user;
    },
    async signIn() {
      user = {
        email: "demo@example.com",
        emailVerified: true,
        name: "Demo member",
      };
      listeners.forEach((fn) => fn());
    },
    async signOut() {
      user = null;
      listeners.forEach((fn) => fn());
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}
