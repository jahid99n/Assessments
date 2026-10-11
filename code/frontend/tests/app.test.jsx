import { cloneElement } from "react";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it, vi } from "vitest";
import App from "../src/App.jsx";
import { RuntimeProvider } from "../src/runtime.jsx";
import { createDemoApi, createDemoAuth, DEMO_KEY } from "../src/lib/demo.js";
import { currentMonth } from "../src/lib/format.js";

vi.mock("recharts", async (importOriginal) => ({
  ...(await importOriginal()),
  ResponsiveContainer: ({ children }) =>
    cloneElement(children, { width: 600, height: 250 }),
}));

// Compile the real lazy chart module before timing DOM assertions. Cold Vite
// compilation is not a UI response-time test; browser tests cover lazy loading.
beforeAll(async () => {
  await import("../src/pages/Dashboard.jsx");
}, 30000);

function mount(path = "/", overrides = {}) {
  const api = createDemoApi();
  const runtime = {
    api,
    auth: createDemoAuth(),
    demo: true,
    upload: api.simulateUpload,
    ...overrides,
  };
  const view = render(
    <RuntimeProvider runtime={runtime}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </RuntimeProvider>,
  );
  return { ...view, api: runtime.api, runtime, user: userEvent.setup() };
}
async function fillExpense(user, merchant = "Test merchant") {
  await user.type(screen.getByLabelText("Merchant"), merchant);
  await user.type(screen.getByLabelText("Total (AUD)"), "12.50");
}

describe("dashboard and authentication", () => {
  it("renders cards, accessible chart summaries and demo label", async () => {
    mount();
    expect(
      await screen.findByRole("heading", { name: "Spending over time" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Total spent")).toBeInTheDocument();
    expect(screen.getByText("DEMO WORKSPACE")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Monthly spending:/ }),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("guards private routes and provides managed registration entry", async () => {
    const signIn = vi.fn();
    mount("/expenses", {
      demo: false,
      auth: { session: async () => null, subscribe: () => () => {}, signIn },
    });
    expect(
      await screen.findByRole("button", { name: "Sign in with Cognito" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Your expenses" }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Create an account with Cognito" }),
    );
    expect(signIn).toHaveBeenCalled();
    expect(
      screen.getByText(/Cognito handles registration/),
    ).toBeInTheDocument();
  });
  it("shows configuration failure without trying AWS", async () => {
    mount("/login", {
      demo: false,
      configurationError: "AWS connection is not configured.",
      auth: { session: async () => null, subscribe: () => () => {} },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not configured",
    );
    expect(
      screen.getByRole("button", { name: "Sign in with Cognito" }),
    ).toBeDisabled();
  });
  it("signs out and allows entering demo again", async () => {
    const { user } = mount();
    await screen.findByRole("heading", { name: "Spending over time" });
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(
      await screen.findByRole("button", { name: "Enter local demo" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Enter local demo" }));
    expect(
      await screen.findByRole("heading", { name: "Spending over time" }),
    ).toBeInTheDocument();
  });
  it("displays API error with retry action", async () => {
    const api = createDemoApi();
    api.stats = vi.fn().mockRejectedValue(new Error("Service unavailable"));
    mount("/", { api });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Service unavailable",
    );
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
  });
});

describe("expense interactions", () => {
  it("creates an expense through a labelled modal", async () => {
    const { user } = mount("/expenses");
    await screen.findByRole("button", { name: "View Coles" });
    await user.click(screen.getByRole("button", { name: "Add expense" }));
    expect(
      screen.getByRole("dialog", { name: "Add an expense" }),
    ).toBeInTheDocument();
    await fillExpense(user);
    await user.click(screen.getByRole("button", { name: "Save expense" }));
    expect(
      await screen.findByRole("button", { name: "Edit Test merchant" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Expense saved.")).toBeInTheDocument();
  });
  it("edits a completed expense", async () => {
    const { user } = mount("/expenses");
    await user.click(await screen.findByRole("button", { name: "Edit Coles" }));
    const merchant = screen.getByLabelText("Merchant");
    await user.clear(merchant);
    await user.type(merchant, "Edited merchant");
    await user.click(screen.getByRole("button", { name: "Save expense" }));
    expect(
      await screen.findByRole("button", { name: "Edit Edited merchant" }),
    ).toBeInTheDocument();
  });
  it("requires confirmation before deletion", async () => {
    const { user } = mount("/expenses");
    await user.click(
      await screen.findByRole("button", { name: "Delete The Grounds Café" }),
    );
    const dialog = screen.getByRole("dialog", { name: "Delete expense?" });
    expect(
      screen.getByRole("button", { name: "Edit The Grounds Café" }),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", {
        name: "Delete expense",
        exact: true,
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Edit The Grounds Café" }),
      ).not.toBeInTheDocument(),
    );
  });
  it("filters by category and labels loaded-only search", async () => {
    const { user } = mount("/expenses");
    await screen.findByRole("button", { name: "Edit Coles" });
    await user.selectOptions(screen.getByLabelText("Category"), "Transport");
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Edit Coles" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      await screen.findByRole("button", { name: "Edit Shell" }),
    ).toBeInTheDocument();
    await user.type(
      screen.getByLabelText("Search loaded expenses"),
      "nothing matches",
    );
    expect(
      screen.getByRole("heading", { name: "No matching expenses loaded" }),
    ).toBeInTheDocument();
  });
  it("supports loading additional backend pages", async () => {
    const { user } = mount("/expenses");
    await screen.findByRole("button", { name: "Edit Coles" });
    expect(
      screen.queryByRole("button", { name: "Edit Morning coffee" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Load more expenses" }),
    );
    expect(
      await screen.findByRole("button", { name: "Edit Morning coffee" }),
    ).toBeInTheDocument();
  });
  it("supports an empty page that still has a cursor", async () => {
    const api = createDemoApi();
    api.list = vi
      .fn()
      .mockResolvedValueOnce({ items: [], nextCursor: "next" })
      .mockResolvedValueOnce({ items: [] });
    const { user } = mount("/expenses", { api });
    expect(
      await screen.findByRole("button", { name: "Load more expenses" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Load more expenses" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Load more expenses" }),
      ).not.toBeInTheDocument(),
    );
  });
  it("displays a true empty state", async () => {
    localStorage.setItem(
      DEMO_KEY,
      JSON.stringify({ expenses: [], budgets: {}, weeklySummary: false }),
    );
    mount("/expenses");
    expect(
      await screen.findByRole("heading", { name: "No expenses loaded" }),
    ).toBeInTheDocument();
  });
  it("loads expense details", async () => {
    const { user } = mount("/expenses");
    await user.click(await screen.findByRole("button", { name: "View Coles" }));
    expect(await screen.findByText("Not provided")).toBeInTheDocument();
    expect(
      screen.getByRole("dialog", { name: "Expense details" }),
    ).toBeInTheDocument();
  });
});

describe("budget and receipt pages", () => {
  it("updates the selected month budget", async () => {
    const { user, api } = mount("/budget");
    const limit = await screen.findByLabelText("Monthly spending limit (AUD)");
    await user.clear(limit);
    await user.type(limit, "1800");
    await user.click(screen.getByRole("button", { name: "Save budget" }));
    expect(
      await screen.findByText("Budget and preferences saved."),
    ).toBeInTheDocument();
    expect((await api.budget(currentMonth())).monthlyLimit).toBe(1800);
  });
  it("changes month without carrying over the previous limit", async () => {
    mount("/budget");
    await screen.findByLabelText("Monthly spending limit (AUD)");
    fireEvent.change(screen.getByLabelText("Budget month"), {
      target: { value: "2020-01" },
    });
    await waitFor(() =>
      expect(screen.getByLabelText("Monthly spending limit (AUD)")).toHaveValue(
        "0",
      ),
    );
  });
  it("rejects an invalid file before asking for permission", async () => {
    const api = createDemoApi();
    api.uploadPermission = vi.fn();
    mount("/receipts", { api });
    const input = await screen.findByLabelText("Receipt image");
    fireEvent.change(input, {
      target: {
        files: [new File(["x"], "x.pdf", { type: "application/pdf" })],
      },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("JPEG or PNG");
    expect(api.uploadPermission).not.toHaveBeenCalled();
  });
  it.each(["PROCESSED", "FAILED"])(
    "renders confirmed %s receipt outcome",
    async (status) => {
      const api = createDemoApi();
      api.detail = vi.fn(async () => ({
        expenseId: "demo-id",
        status,
        merchant: "Simulated receipt",
        total: 28,
        errorMessage: status === "FAILED" ? "Missing total" : undefined,
      }));
      const { user } = mount("/receipts", {
        api,
        upload: async (_permission, _file, { onProgress }) => onProgress(100),
      });
      const input = await screen.findByLabelText("Receipt image");
      await user.upload(input, new File(["x"], "r.png", { type: "image/png" }));
      await user.click(
        screen.getByRole("button", { name: "Simulate receipt upload" }),
      );
      expect(
        await screen.findByRole("heading", {
          name:
            status === "PROCESSED"
              ? "Demo receipt completed"
              : "Receipt could not be processed",
        }),
      ).toBeInTheDocument();
    },
  );
  it("shows upload error and permits checking the existing record", async () => {
    const { user } = mount("/receipts", {
      upload: async () => {
        throw new Error("Upload rejected");
      },
    });
    await user.upload(
      await screen.findByLabelText("Receipt image"),
      new File(["x"], "r.png", { type: "image/png" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Simulate receipt upload" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Upload rejected",
    );
    expect(
      screen.getByRole("button", { name: "Check receipt status" }),
    ).toBeInTheDocument();
  });
});
