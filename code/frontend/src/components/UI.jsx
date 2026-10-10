import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { money } from "../lib/format.js";

export function useResource(load) {
  const [state, setState] = useState({ loading: true, data: null, error: "" });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, data: null, error: "" });
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ loading: false, data, error: "" });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState({
            loading: false,
            data: null,
            error: error.message || "Unable to load this view.",
          });
      });
    return () => controller.abort();
  }, [load, revision]);
  return {
    ...state,
    refresh: useCallback(() => setRevision((v) => v + 1), []),
  };
}
export function ErrorNotice({ children, retry }) {
  return (
    <div className="notice error" role="alert">
      <Icon name="info" />
      <div>
        {children}
        {retry && (
          <button className="text-button" onClick={retry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
export function Loading({ text = "Loading your expenses…" }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {text}
    </div>
  );
}
export function Empty({ title = "No expenses here yet", children }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon name="receipt" size={28} />
      </div>
      <h3>{title}</h3>
      <p>
        {children ||
          "Add an expense or upload your first receipt to get started."}
      </p>
    </div>
  );
}
export function PageHeading({ eyebrow, title, description, action }) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="subheading">{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Status({ value }) {
  const labels = {
    PENDING: "Pending",
    PROCESSING: "Processing",
    PROCESSED: "Completed",
    FAILED: "Failed",
  };
  return (
    <span className={`status status-${value?.toLowerCase()}`}>
      <span />
      {labels[value] || "Unknown"}
    </span>
  );
}
export function BudgetBar({ spent, limit }) {
  const percent = limit > 0 ? (spent / limit) * 100 : null;
  const over = spent > limit;
  return (
    <div className={`budget-meter ${over ? "over" : ""}`}>
      <div className="split">
        <span>
          {percent === null
            ? "No positive budget set"
            : `${percent.toFixed(1)}% used`}
        </span>
        <strong>{money(limit)}</strong>
      </div>
      <div
        className="meter-track"
        role="progressbar"
        aria-label="Monthly budget utilisation"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={
          percent === null ? 0 : Math.min(100, Math.round(percent))
        }
        aria-valuetext={
          percent === null
            ? "No positive budget set"
            : `${percent.toFixed(1)} percent used`
        }
      >
        <span
          style={{
            width: `${Math.min(100, Math.max(0, percent ?? (spent ? 100 : 0)))}%`,
          }}
        />
      </div>
      <p>
        {over
          ? `${money(spent - limit)} over your budget`
          : `${money(limit - spent)} available to spend`}
      </p>
    </div>
  );
}
export function Modal({ title, onClose, children, busy = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    dialog.showModal();
    dialog.querySelector('input:not([type="checkbox"]), select')?.focus();
    return () => {
      dialog.close();
      previous?.focus?.();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby="modal-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="dialog-heading">
        <h2 id="modal-title">{title}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
          disabled={busy}
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
