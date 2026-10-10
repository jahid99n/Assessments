import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import {
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { useRuntime } from "../runtime.jsx";
import { allExpenses } from "../lib/api.js";
import { colours, currentMonth, money, monthLabel } from "../lib/format.js";
import {
  BudgetBar,
  Empty,
  ErrorNotice,
  Loading,
  PageHeading,
  useResource,
} from "../components/UI.jsx";
import { ExpenseDialog, ExpenseTable } from "../components/Expenses.jsx";
import Icon from "../components/Icon.jsx";

export default function Dashboard() {
  const { api } = useRuntime();
  const month = currentMonth();
  const load = useCallback(
    async (signal) => {
      const [stats, items] = await Promise.all([
        api.stats(signal),
        allExpenses(api, { month }, signal),
      ]);
      return {
        stats,
        recent: items
          .sort((a, b) =>
            (b.receiptDate || "").localeCompare(a.receiptDate || ""),
          )
          .slice(0, 5),
      };
    },
    [api, month],
  );
  const { loading, data, error, refresh } = useResource(load);
  const [dialog, setDialog] = useState(null);
  const [message, setMessage] = useState("");
  const action = (
    <button
      className="button primary"
      onClick={() => setDialog({ action: "create" })}
    >
      <Icon name="plus" />
      Add expense
    </button>
  );
  return (
    <>
      <PageHeading
        eyebrow="YOUR MONEY, AT A GLANCE"
        title="A clearer picture of your spending."
        description={`Here’s where you stand in ${monthLabel(month)}.`}
        action={action}
      />
      {message && (
        <div className="notice success" role="status">
          {message}
        </div>
      )}
      {loading ? (
        <Loading text="Preparing your overview…" />
      ) : error ? (
        <ErrorNotice retry={refresh}>{error}</ErrorNotice>
      ) : (
        data && (
          <>
            <div className="summary-grid">
              {[
                [
                  "Total spent",
                  data.stats.thisMonth.total,
                  "This month · AUD",
                  "wallet",
                ],
                [
                  "Monthly budget",
                  data.stats.thisMonth.budget,
                  "Your monthly spending limit",
                  "shield",
                ],
                [
                  "Remaining",
                  data.stats.thisMonth.remaining,
                  data.stats.thisMonth.remaining < 0
                    ? "Over your monthly budget"
                    : "Room in your budget",
                  "trend",
                ],
                [
                  "Expenses",
                  data.stats.thisMonth.count,
                  "Completed transactions this month",
                  "receipt",
                ],
              ].map(([label, value, note, icon], i) => (
                <article
                  key={label}
                  className={`summary-card ${i === 0 ? "featured" : ""}`}
                >
                  <div className="split">
                    <span>{label}</span>
                    <span className="card-icon">
                      <Icon name={icon} />
                    </span>
                  </div>
                  <strong
                    className={`summary-value ${value < 0 ? "negative" : ""}`}
                  >
                    {i === 3 ? value : money(value)}
                  </strong>
                  <small>{note}</small>
                </article>
              ))}
            </div>
            <div className="dashboard-main">
              <section className="panel trend-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Spending over time</h2>
                    <p>A little perspective on the bigger picture.</p>
                  </div>
                  <span className="pill">Last 6 months</span>
                </div>
                <div
                  className="chart"
                  role="img"
                  aria-label={`Monthly spending: ${Object.entries(
                    data.stats.byMonth,
                  )
                    .map(([m, v]) => `${monthLabel(m)} ${money(v)}`)
                    .join("; ")}`}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={Object.entries(data.stats.byMonth).map(
                        ([m, total]) => ({
                          month: monthLabel(m).split(" ")[0].slice(0, 3),
                          total,
                        }),
                      )}
                      margin={{ top: 12, right: 12, left: 0, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="spend-fill"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#218b84"
                            stopOpacity={0.2}
                          />
                          <stop
                            offset="100%"
                            stopColor="#218b84"
                            stopOpacity={0.01}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        vertical={false}
                        stroke="#e9eef1"
                        strokeDasharray="3 5"
                      />
                      <XAxis
                        dataKey="month"
                        axisLine={false}
                        tickLine={false}
                        tickMargin={12}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        width={55}
                        tickFormatter={(v) => `$${v}`}
                      />
                      <Tooltip
                        formatter={(value) => [money(value), "Spending"]}
                      />
                      <Area
                        type="monotone"
                        dataKey="total"
                        stroke="#147b74"
                        strokeWidth={3}
                        fill="url(#spend-fill)"
                        dot={{ r: 4, fill: "#fff", strokeWidth: 2 }}
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <p className="chart-caption">
                  Monthly totals · Australian dollars · current month is partial
                </p>
              </section>
              <section className="panel categories-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Where it goes</h2>
                    <p>Spending by category</p>
                  </div>
                </div>
                {Object.keys(data.stats.byCategory).length ? (
                  <>
                    <div
                      className="donut"
                      role="img"
                      aria-label={`Category spending: ${Object.entries(
                        data.stats.byCategory,
                      )
                        .map(([c, v]) => `${c} ${money(v)}`)
                        .join("; ")}`}
                    >
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={Object.entries(data.stats.byCategory).map(
                              ([name, value]) => ({ name, value }),
                            )}
                            innerRadius={62}
                            outerRadius={83}
                            paddingAngle={4}
                            dataKey="value"
                            stroke="none"
                            isAnimationActive={false}
                          >
                            {Object.keys(data.stats.byCategory).map(
                              (category) => (
                                <Cell
                                  key={category}
                                  fill={colours[category] || colours.Other}
                                />
                              ),
                            )}
                          </Pie>
                          <Tooltip formatter={(value) => money(value)} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="donut-label">
                        <small>THIS MONTH</small>
                        <strong>{money(data.stats.thisMonth.total)}</strong>
                      </div>
                    </div>
                    <ul className="category-legend">
                      {Object.entries(data.stats.byCategory).map(
                        ([category, value]) => (
                          <li key={category}>
                            <span>
                              <i
                                style={{
                                  background:
                                    colours[category] || colours.Other,
                                }}
                              />
                              {category}
                            </span>
                            <strong>{money(value)}</strong>
                          </li>
                        ),
                      )}
                    </ul>
                  </>
                ) : (
                  <Empty title="Your categories will appear here" />
                )}
              </section>
            </div>
            <div className="dashboard-bottom">
              <section className="panel transactions-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Recent transactions</h2>
                    <p>Your latest expenses this month.</p>
                  </div>
                  <Link className="text-link" to="/expenses">
                    View all <Icon name="arrow" size={16} />
                  </Link>
                </div>
                <ExpenseTable
                  items={data.recent}
                  compact
                  onAction={(action, item) => setDialog({ action, item })}
                />
              </section>
              <div className="side-panels">
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Budget check-in</h2>
                    <Icon name="wallet" />
                  </div>
                  <BudgetBar
                    spent={data.stats.thisMonth.total}
                    limit={data.stats.thisMonth.budget}
                  />
                  <Link className="text-link" to="/budget">
                    Manage your budget <Icon name="arrow" size={16} />
                  </Link>
                </section>
                <section className="upload-promo">
                  <span className="promo-icon">
                    <Icon name="receipt" size={26} />
                  </span>
                  <h2>
                    Less typing.
                    <br />
                    More living.
                  </h2>
                  <p>
                    Turn a receipt into an expense. Upload, review, and you’re
                    done.
                  </p>
                  <Link className="button light" to="/receipts">
                    Upload a receipt <Icon name="arrow" size={16} />
                  </Link>
                </section>
              </div>
            </div>
          </>
        )
      )}
      {dialog && (
        <ExpenseDialog
          {...dialog}
          onClose={() => setDialog(null)}
          onSaved={(text) => {
            setDialog(null);
            setMessage(text);
            refresh();
          }}
        />
      )}
    </>
  );
}
