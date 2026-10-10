import { useEffect, useRef, useState } from "react";
import { useRuntime } from "../runtime.jsx";
import {
  categories,
  dateLabel,
  money,
  sydneyDay,
  validateExpense,
} from "../lib/format.js";
import { Empty, ErrorNotice, Loading, Modal, Status } from "./UI.jsx";

export function ExpenseTable({ items, onAction, compact = false }) {
  if (!items.length) return <Empty />;
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">Expenses in Australian dollars</caption>
        <thead>
          <tr>
            <th>Merchant</th>
            <th>Date</th>
            <th>Category</th>
            <th>Status</th>
            <th className="numeric">Amount</th>
            {onAction && (
              <th>
                <span className="sr-only">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.expenseId}>
              <td>
                <div className="merchant">
                  <span
                    className={`merchant-icon cat-${item.category?.toLowerCase() || "other"}`}
                  >
                    {(item.merchant || "R").slice(0, 1)}
                  </span>
                  <div>
                    <strong>{item.merchant || "Receipt upload"}</strong>
                    <small>
                      {item.source === "receipt" ? "Receipt" : "Manual entry"}
                    </small>
                  </div>
                </div>
              </td>
              <td>{dateLabel(item.receiptDate)}</td>
              <td>
                <span className="category-label">{item.category || "—"}</span>
              </td>
              <td>
                <Status value={item.status} />
              </td>
              <td className="numeric amount">
                {item.total === undefined ? "—" : money(item.total)}
              </td>
              {onAction && (
                <td>
                  <div className="row-actions">
                    <button
                      onClick={() => onAction("detail", item)}
                      aria-label={`View ${item.merchant || "receipt"}`}
                    >
                      View
                    </button>
                    {!compact && item.status === "PROCESSED" && (
                      <button
                        onClick={() => onAction("edit", item)}
                        aria-label={`Edit ${item.merchant}`}
                      >
                        Edit
                      </button>
                    )}
                    {!compact && (
                      <button
                        className="danger-text"
                        onClick={() => onAction("delete", item)}
                        aria-label={`Delete ${item.merchant || "receipt"}`}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExpenseDialog({ action, item, onClose, onSaved }) {
  const { api, demo } = useRuntime();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState(null);
  const controller = useRef(null);
  const [form, setForm] = useState({
    merchant: item?.merchant || "",
    receiptDate: item?.receiptDate || sydneyDay(),
    total: item?.total === undefined ? "" : String(item.total),
    gst: item?.gst === undefined ? "" : String(item.gst),
    category: item?.category || "Other",
  });
  useEffect(() => {
    const active = new AbortController();
    controller.current = active;
    if (action === "detail")
      api
        .detail(item.expenseId, active.signal)
        .then((value) => {
          if (!active.signal.aborted) setDetail(value);
        })
        .catch((e) => {
          if (!active.signal.aborted) setError(e.message);
        });
    return () => active.abort();
  }, [api, action, item?.expenseId]);
  const set = (key) => (event) =>
    setForm((old) => ({ ...old, [key]: event.target.value }));
  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (action === "delete")
        await api.remove(item.expenseId, controller.current.signal);
      else {
        const data = validateExpense(form);
        if (action === "edit")
          await api.update(item.expenseId, data, controller.current.signal);
        else await api.create(data, controller.current.signal);
      }
      if (!controller.current.signal.aborted)
        onSaved(action === "delete" ? "Expense deleted." : "Expense saved.");
    } catch (e) {
      if (!controller.current.signal.aborted) setError(e.message);
    } finally {
      if (!controller.current.signal.aborted) setBusy(false);
    }
  }
  return (
    <Modal
      title={
        {
          create: "Add an expense",
          edit: "Edit expense",
          delete: "Delete expense?",
          detail: "Expense details",
        }[action]
      }
      onClose={onClose}
      busy={busy}
    >
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {action === "detail" ? (
        !detail && !error ? (
          <Loading />
        ) : (
          detail && (
            <div className="detail">
              <div className="detail-total">
                {detail.total === undefined
                  ? "Awaiting extraction"
                  : money(detail.total)}
              </div>
              <h3>{detail.merchant || "Receipt upload"}</h3>
              <Status value={detail.status} />
              <dl>
                <dt>Date</dt>
                <dd>{dateLabel(detail.receiptDate)}</dd>
                <dt>Category</dt>
                <dd>{detail.category || "Not extracted"}</dd>
                <dt>Source</dt>
                <dd>{detail.source}</dd>
                <dt>GST</dt>
                <dd>
                  {detail.gst === undefined
                    ? "Not provided"
                    : money(detail.gst)}
                </dd>
                <dt>Currency</dt>
                <dd>
                  {detail.currency || "Not extracted"}
                  {detail.currencySource === "application_default" &&
                    " (application default)"}
                </dd>
                {detail.confidence !== undefined && (
                  <>
                    <dt>Extraction confidence</dt>
                    <dd>{Number(detail.confidence).toFixed(1)}%</dd>
                  </>
                )}
              </dl>
              {detail.errorMessage && (
                <ErrorNotice>{detail.errorMessage}</ErrorNotice>
              )}
              {detail.status === "FAILED" && (
                <p className="muted">
                  {detail.retryable
                    ? "Processing may retry automatically. If it stays failed, ask the operator to replay the original event."
                    : "Upload a clearer, corrected receipt. Failed records cannot be edited."}
                </p>
              )}
              {detail.imageUrl && /^https:\/\//.test(detail.imageUrl) && (
                <a
                  className="button secondary"
                  href={detail.imageUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open receipt image ↗
                </a>
              )}
              {demo && detail.source === "receipt" && (
                <p className="muted">
                  Demonstration record. No real receipt image or AWS extraction.
                </p>
              )}
            </div>
          )
        )
      ) : (
        <form onSubmit={submit}>
          {action === "delete" ? (
            <p>
              Delete <strong>{item.merchant || "this receipt"}</strong>
              {item.total !== undefined ? ` (${money(item.total)})` : ""}? It
              will be removed from your spending and its receipt image will be
              deleted. This cannot be undone.
            </p>
          ) : (
            <div className="form-grid">
              <label className="full">
                Merchant
                <input
                  required
                  maxLength={200}
                  value={form.merchant}
                  onChange={set("merchant")}
                  placeholder="e.g. Coles"
                />
              </label>
              <label>
                Transaction date
                <input
                  required
                  type="date"
                  value={form.receiptDate}
                  onChange={set("receiptDate")}
                />
              </label>
              <label>
                Category
                <select
                  aria-label="Category"
                  value={form.category}
                  onChange={set("category")}
                >
                  {categories.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label>
                Total (AUD)
                <input
                  required
                  inputMode="decimal"
                  value={form.total}
                  onChange={set("total")}
                  placeholder="0.00"
                />
              </label>
              <label>
                GST (optional)
                <input
                  inputMode="decimal"
                  value={form.gst}
                  onChange={set("gst")}
                  placeholder="0.00"
                />
              </label>
              <p className="form-hint full">
                Use the receipt total, including GST. All amounts are in
                Australian dollars.
                {action === "edit" &&
                  item.gst !== undefined &&
                  " Leaving GST blank keeps its existing value; enter 0 to set it to zero."}
              </p>
            </div>
          )}
          <div className="dialog-actions">
            <button
              className="button secondary"
              type="button"
              onClick={onClose}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              className={`button ${action === "delete" ? "danger" : "primary"}`}
              disabled={busy}
            >
              {busy
                ? "Saving…"
                : action === "delete"
                  ? "Delete expense"
                  : "Save expense"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
