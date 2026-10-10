import { useCallback, useEffect, useRef, useState } from "react";
import { useRuntime } from "../runtime.jsx";
import { categories } from "../lib/format.js";
import { Empty, ErrorNotice, Loading, PageHeading } from "../components/UI.jsx";
import { ExpenseDialog, ExpenseTable } from "../components/Expenses.jsx";
import Icon from "../components/Icon.jsx";

export default function ExpensesPage() {
  const { api } = useRuntime();
  const [filters, setFilters] = useState({ category: "", from: "", to: "" });
  const [search, setSearch] = useState("");
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState(null);
  const [message, setMessage] = useState("");
  const [revision, setRevision] = useState(0);
  const active = useRef(null);
  const load = useCallback(
    async (next, reset = false) => {
      active.current?.abort();
      const controller = new AbortController();
      active.current = controller;
      setLoading(true);
      setError("");
      if (reset) {
        setItems([]);
        setCursor(undefined);
      }
      if (filters.from && filters.to && filters.from > filters.to) {
        setError("The start date must be before the end date.");
        setLoading(false);
        return;
      }
      try {
        const page = await api.list(
          { ...filters, limit: 10, cursor: next },
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setItems((old) => [
            ...new Map(
              [...(reset ? [] : old), ...page.items].map((e) => [
                e.expenseId,
                e,
              ]),
            ).values(),
          ]);
          setCursor(page.nextCursor);
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(e.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    },
    [api, filters],
  );
  useEffect(() => {
    load(undefined, true);
    return () => active.current?.abort();
  }, [load, revision]);
  const shown = items
    .filter((e) =>
      (e.merchant || "receipt upload")
        .toLowerCase()
        .includes(search.toLowerCase()),
    )
    .sort((a, b) => (b.receiptDate || "").localeCompare(a.receiptDate || ""));
  return (
    <>
      <PageHeading
        eyebrow="THE DETAILS THAT ADD UP"
        title="Your expenses"
        description="Every purchase, in one place. All amounts in AUD."
        action={
          <button
            className="button primary"
            onClick={() => setDialog({ action: "create" })}
          >
            <Icon name="plus" />
            Add expense
          </button>
        }
      />
      {message && (
        <div className="notice success" role="status">
          {message}
        </div>
      )}
      <section className="panel">
        <div className="filter-bar">
          <label className="search-field">
            Search loaded expenses
            <div>
              <Icon name="search" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search merchants…"
              />
            </div>
          </label>
          <label>
            Category
            <select
              aria-label="Category"
              value={filters.category}
              onChange={(e) =>
                setFilters((f) => ({ ...f, category: e.target.value }))
              }
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            From
            <input
              type="date"
              value={filters.from}
              onChange={(e) =>
                setFilters((f) => ({ ...f, from: e.target.value }))
              }
            />
          </label>
          <label>
            To
            <input
              type="date"
              value={filters.to}
              onChange={(e) =>
                setFilters((f) => ({ ...f, to: e.target.value }))
              }
            />
          </label>
          <button
            className="button secondary"
            onClick={() => {
              setSearch("");
              setFilters({ category: "", from: "", to: "" });
            }}
          >
            Reset
          </button>
        </div>
        <p className="filter-note">
          Search covers the {items.length} loaded expenses only. Load more to
          search additional records. Dates sort within loaded results.
        </p>
        {error && (
          <ErrorNotice retry={() => load(cursor, !items.length)}>
            {error}
          </ErrorNotice>
        )}
        {shown.length ? (
          <ExpenseTable
            items={shown}
            onAction={(action, item) => setDialog({ action, item })}
          />
        ) : (
          !loading && (
            <Empty
              title={
                search || filters.category || filters.from || filters.to
                  ? "No matching expenses loaded"
                  : "No expenses loaded"
              }
            >
              {cursor
                ? "This page has no matches. Continue loading to check the next page."
                : "Try changing your filters or add an expense."}
            </Empty>
          )
        )}
        {loading && <Loading />}
        <div className="table-footer">
          <span>
            {shown.length} shown · {items.length} loaded
          </span>
          {cursor && (
            <button
              className="button secondary"
              disabled={loading}
              onClick={() => load(cursor)}
            >
              Load more expenses
            </button>
          )}
          {!cursor && !loading && <span>All matching pages loaded</span>}
        </div>
      </section>
      {dialog && (
        <ExpenseDialog
          {...dialog}
          onClose={() => setDialog(null)}
          onSaved={(text) => {
            setDialog(null);
            setMessage(text);
            setRevision((v) => v + 1);
          }}
        />
      )}
    </>
  );
}
