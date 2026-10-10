import { useCallback, useEffect, useRef, useState } from "react";
import { useRuntime } from "../runtime.jsx";
import { amount, currentMonth, money, monthLabel } from "../lib/format.js";
import {
  BudgetBar,
  ErrorNotice,
  Loading,
  PageHeading,
  useResource,
} from "../components/UI.jsx";
import Icon from "../components/Icon.jsx";

function BudgetEditor({ month }) {
  const { api, user, demo } = useRuntime();
  const load = useCallback((signal) => api.budget(month, signal), [api, month]);
  const { loading, data, error, refresh } = useResource(load);
  const [limit, setLimit] = useState("");
  const [weekly, setWeekly] = useState(false);
  const [subscribe, setSubscribe] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [message, setMessage] = useState("");
  const controller = useRef(null);
  useEffect(() => {
    if (data) {
      setLimit(String(data.monthlyLimit));
      setWeekly(data.weeklySummary);
    }
  }, [data]);
  useEffect(() => {
    controller.current = new AbortController();
    return () => controller.current.abort();
  }, []);
  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setSaveError("");
    setMessage("");
    try {
      const payload = {
        month,
        monthlyLimit: amount(limit),
        weeklySummary: weekly,
      };
      if (subscribe) {
        if (!user.emailVerified || !user.email)
          throw new Error("Verify your Cognito email before subscribing.");
        payload.email = user.email;
      }
      if (weekly && !subscribe && data.subscriptionStatus === "not_subscribed")
        throw new Error(
          "Enable email notifications first to receive weekly summaries.",
        );
      await api.saveBudget(payload, controller.current.signal);
      if (!controller.current.signal.aborted) {
        setMessage("Budget and preferences saved.");
        refresh();
      }
    } catch (err) {
      if (!controller.current.signal.aborted) setSaveError(err.message);
    } finally {
      if (!controller.current.signal.aborted) setSaving(false);
    }
  }
  if (loading) return <Loading text="Loading this month’s budget…" />;
  if (error) return <ErrorNotice retry={refresh}>{error}</ErrorNotice>;
  const labels = {
    not_subscribed: "Not subscribed",
    pending_or_blocked: "Pending confirmation or blocked",
    confirmed: "Confirmed and verified",
  };
  return (
    <div className="budget-grid">
      <section className="panel budget-form">
        <div className="panel-heading">
          <div>
            <h2>Make room for what matters.</h2>
            <p>{monthLabel(month)} · AUD</p>
          </div>
          <span className="card-icon">
            <Icon name="wallet" />
          </span>
        </div>
        {message && (
          <div className="notice success" role="status">
            {message}
          </div>
        )}
        {saveError && <ErrorNotice>{saveError}</ErrorNotice>}
        <form onSubmit={save}>
          <label htmlFor="budget-limit">Monthly spending limit (AUD)</label>
          <div className="currency-input">
            <span aria-hidden="true">$</span>
            <input
              id="budget-limit"
              required
              inputMode="decimal"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
          </div>
          <p className="form-hint">
            A budget applies to this month only. It does not automatically roll
            over.
          </p>
          <div className="form-divider" />
          <h3>Email preferences</h3>
          <p className="muted">
            Optional alerts and a weekly spending check-in.
          </p>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={subscribe}
              onChange={(e) => setSubscribe(e.target.checked)}
              disabled={!user.emailVerified}
            />
            <span>
              Subscribe or reconnect my verified email
              <small>{user.email || "No verified email available"}</small>
            </span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={weekly}
              onChange={(e) => setWeekly(e.target.checked)}
            />
            <span>
              Send me a weekly summary
              <small>Mondays at 9:00 am, Australia/Sydney</small>
            </span>
          </label>
          <button className="button primary" disabled={saving}>
            {saving ? "Saving…" : "Save budget"}
          </button>
        </form>
      </section>
      <div>
        <section className="panel budget-overview">
          <div className="panel-heading">
            <h2>This month’s balance</h2>
            <Icon name="trend" />
          </div>
          <div className="balance-number">{money(data.remaining)}</div>
          <p className="muted">
            {data.remaining < 0 ? "over budget" : "remaining in your budget"}
          </p>
          <BudgetBar spent={data.spent} limit={data.monthlyLimit} />
          <dl>
            <dt>Spent so far</dt>
            <dd>{money(data.spent)}</dd>
            <dt>Monthly budget</dt>
            <dd>{money(data.monthlyLimit)}</dd>
          </dl>
          {data.remaining < 0 && (
            <div className="notice error">
              <Icon name="info" />
              Spending has exceeded this month’s limit.
            </div>
          )}
        </section>
        <section className="panel notification-panel">
          <div className="panel-heading">
            <h2>Stay in the loop</h2>
            <Icon name="bell" />
          </div>
          <p className="subscription-label">
            {demo
              ? "Demo only · no emails are sent"
              : labels[data.subscriptionStatus] || "Status unavailable"}
          </p>
          <p>
            After subscribing, open the SNS confirmation email and confirm your
            subscription. New subscriptions have a 15-minute safety hold.
          </p>
          <p>
            Pending or unsafe subscriptions can block delivery. Confirmation
            does not guarantee an email was delivered.
          </p>
          <p className="muted">
            Turning off weekly summaries does not unsubscribe budget alerts. Use
            the unsubscribe link in an SNS email to stop those.
          </p>
          <button className="text-button" onClick={refresh}>
            Refresh notification status
          </button>
        </section>
      </div>
    </div>
  );
}

export default function BudgetPage() {
  const [month, setMonth] = useState(currentMonth());
  return (
    <>
      <PageHeading
        eyebrow="A PLAN FOR YOUR MONEY"
        title="Spend with a little more intention."
        description="Set a monthly limit that works for you."
        action={
          <label className="month-picker">
            Budget month
            <input
              type="month"
              required
              value={month}
              onChange={(e) => {
                if (/^\d{4}-\d{2}$/.test(e.target.value))
                  setMonth(e.target.value);
              }}
            />
          </label>
        }
      />
      <BudgetEditor key={month} month={month} />
    </>
  );
}
