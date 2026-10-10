import { lazy, Suspense, useEffect, useState } from "react";
import {
  Link,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { useRuntime } from "./runtime.jsx";
import { ErrorNotice, Loading } from "./components/UI.jsx";
import Icon from "./components/Icon.jsx";
import ExpensesPage from "./pages/ExpensesPage.jsx";
import ReceiptPage from "./pages/ReceiptPage.jsx";
import BudgetPage from "./pages/BudgetPage.jsx";

const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));

function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <i />
        <i />
        <i />
      </span>
      <span>
        smart expense<span className="brand-sub">A LITTLE MORE CLARITY.</span>
      </span>
    </span>
  );
}
function Login() {
  const { auth, user, loading, error, demo, configurationError } = useRuntime();
  const [issue, setIssue] = useState("");
  const [busy, setBusy] = useState(false);
  if (loading) return <Loading text="Checking your session…" />;
  if (user) return <Navigate to="/" replace />;
  async function signIn() {
    setBusy(true);
    setIssue("");
    try {
      await auth.signIn();
    } catch {
      setIssue(
        "Sign-in could not be started. Please check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <Brand />
        <div>
          <p className="eyebrow">KNOW WHERE YOUR MONEY GOES</p>
          <h1>
            Small expenses.
            <br />A clearer
            <br />
            <em>big picture.</em>
          </h1>
          <p>
            Receipts, budgets and everyday spending.
            <br />
            Together in one thoughtful space.
          </p>
        </div>
        <span>Smart Expense Tracker · ICT5205</span>
      </section>
      <section className="login-form">
        <div>
          <span className="login-symbol">
            <Icon name="wallet" size={34} />
          </span>
          <h2>Welcome to a little more clarity.</h2>
          <p className="subheading">Your spending story starts here.</p>
          {(configurationError || issue || error) && (
            <ErrorNotice>{configurationError || issue || error}</ErrorNotice>
          )}
          {demo && (
            <div className="notice demo-notice">
              Local demonstration · simulated data only. No AWS authentication
              or services.
            </div>
          )}
          <button
            className="button primary"
            onClick={signIn}
            disabled={busy || !!configurationError}
          >
            {busy
              ? "Opening sign-in…"
              : demo
                ? "Enter local demo"
                : "Sign in with Cognito"}
            <Icon name="arrow" size={18} />
          </button>
          {!demo && (
            <>
              <div className="login-divider">New here?</div>
              <button
                className="button secondary"
                onClick={signIn}
                disabled={busy || !!configurationError}
              >
                Create an account with Cognito
              </button>
              <p className="form-hint">
                On the secure Cognito page, choose <strong>Sign up</strong>.
                Cognito handles registration, email verification and password
                recovery. Your password never passes through this app.
              </p>
            </>
          )}
          <div className="login-security">
            <Icon name="shield" size={18} />
            {demo
              ? "Development mode. No real financial data."
              : "Secure sign-in · private expense records"}
          </div>
        </div>
      </section>
    </main>
  );
}
function Protected() {
  const { user, loading } = useRuntime();
  if (loading) return <Loading text="Checking your session…" />;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
function Shell() {
  const { demo, auth, user } = useRuntime();
  const location = useLocation();
  const [error, setError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  useEffect(() => {
    document.getElementById("main-content")?.focus();
  }, [location.pathname]);
  async function logout() {
    setSigningOut(true);
    try {
      await auth.signOut();
    } catch {
      setError("Sign-out could not be completed. Please try again.");
    } finally {
      setSigningOut(false);
    }
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link
          to="/"
          className="brand-link"
          aria-label="Smart Expense Tracker home"
        >
          <Brand />
        </Link>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          {[
            ["/", "grid", "Overview"],
            ["/expenses", "list", "Expenses"],
            ["/receipts", "receipt", "Receipt upload"],
            ["/budget", "wallet", "Budget & alerts"],
          ].map(([path, icon, label]) => (
            <NavLink key={path} aria-label={label} end={path === "/"} to={path}>
              <Icon name={icon} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="small-dot" />
          <p>
            A clearer picture,
            <br />
            one expense at a time.
          </p>
        </div>
        <div className="sidebar-bottom">
          <span className="avatar">
            {demo ? "D" : (user.name || "A").slice(0, 1)}
          </span>
          <div>
            <strong>{demo ? "Demo workspace" : user.name}</strong>
            <small>{demo ? "Local data only" : "Personal account"}</small>
          </div>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <span className="breadcrumb">
            Workspace <span>/</span>{" "}
            <strong>
              {location.pathname === "/"
                ? "Overview"
                : location.pathname === "/expenses"
                  ? "Expenses"
                  : location.pathname === "/receipts"
                    ? "Receipt upload"
                    : "Budget & alerts"}
            </strong>
          </span>
          <span className="region-tag">
            <span />
            AUD · Australia/Sydney
          </span>
          <button
            className="text-button"
            onClick={logout}
            disabled={signingOut}
          >
            <Icon name="logout" size={16} />
            Sign out
          </button>
        </header>
        {demo && (
          <div className="demo-banner">
            <span>
              <strong>DEMO WORKSPACE</strong> Simulated data, saved on this
              device. No AWS services are called.
            </span>
            <span>LOCAL ONLY</span>
          </div>
        )}
        <main id="main-content" tabIndex={-1}>
          {error && <ErrorNotice>{error}</ErrorNotice>}
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>Smart Expense Tracker</span>
          <span>
            {demo
              ? "Made for exploring. All demo data is simulated."
              : "Your money. Your perspective."}
          </span>
        </footer>
      </div>
    </div>
  );
}
export default function App() {
  return (
    <Suspense fallback={<Loading text="Opening your workspace…" />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<Login />} />
        <Route element={<Protected />}>
          <Route element={<Shell />}>
            <Route index element={<Dashboard />} />
            <Route path="expenses" element={<ExpensesPage />} />
            <Route path="receipts" element={<ReceiptPage />} />
            <Route path="budget" element={<BudgetPage />} />
            <Route
              path="*"
              element={
                <section className="panel empty">
                  <h1>Page not found</h1>
                  <Link to="/">Return to overview</Link>
                </section>
              }
            />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
