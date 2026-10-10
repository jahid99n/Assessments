import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useRuntime } from "../runtime.jsx";
import { validateFile, money } from "../lib/format.js";
import { pollReceipt } from "../lib/upload.js";
import { ErrorNotice, PageHeading, Status } from "../components/UI.jsx";
import Icon from "../components/Icon.jsx";

export default function ReceiptPage() {
  const { api, upload, demo } = useRuntime();
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [phase, setPhase] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [item, setItem] = useState(null);
  const [outcome, setOutcome] = useState("success");
  const [dragging, setDragging] = useState(false);
  const active = useRef(null);
  const input = useRef(null);
  const busy = ["uploading", "processing"].includes(phase);
  useEffect(() => () => active.current?.abort(), []);
  function select(value) {
    if (busy) return;
    setError("");
    try {
      validateFile(value);
      setFile(value);
      setPhase("idle");
      setItem(null);
      setProgress(0);
    } catch (e) {
      setFile(null);
      setError(e.message);
    }
  }
  async function monitor(id, signal) {
    setPhase("processing");
    const result = await pollReceipt(api, id, {
      signal,
      onStatus: (value) => {
        if (!signal.aborted) setItem(value);
      },
    });
    if (!signal.aborted)
      setPhase(
        result
          ? result.status === "PROCESSED"
            ? "completed"
            : "failed"
          : "waiting",
      );
  }
  async function start() {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setError("");
    setProgress(0);
    setItem(null);
    setPhase("uploading");
    try {
      validateFile(file);
      const permission = await api.uploadPermission(
        file.type,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setItem({ expenseId: permission.expenseId, status: "PENDING" });
      await upload(permission, file, {
        signal: controller.signal,
        onProgress: setProgress,
        outcome,
      });
      await monitor(permission.expenseId, controller.signal);
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(e.message);
        setPhase("error");
      }
    }
  }
  async function refresh() {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setError("");
    try {
      await monitor(item.expenseId, controller.signal);
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(e.message);
        setPhase("error");
      }
    }
  }
  function cancel() {
    active.current?.abort();
    setPhase("waiting");
  }
  return (
    <>
      <PageHeading
        eyebrow="FROM PAPER TO PICTURE"
        title="Give your receipts a home."
        description="Upload a receipt. Review the details. Get back to your day."
      />
      <div className="receipt-grid">
        <section className="panel receipt-workspace">
          <div className="panel-heading">
            <div>
              <h2>Upload a receipt</h2>
              <p>
                One receipt per image, with the full total and date visible.
              </p>
            </div>
            <span className="pill">JPEG / PNG</span>
          </div>
          {error && <ErrorNotice>{error}</ErrorNotice>}
          <div
            className={`drop-zone ${dragging ? "dragging" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (e.dataTransfer.files.length !== 1) {
                setError("Please upload one receipt at a time.");
                return;
              }
              select(e.dataTransfer.files[0]);
            }}
          >
            <span className="upload-icon">
              <Icon name="up" size={32} />
            </span>
            <h3>{file ? file.name : "Drop your receipt here"}</h3>
            <p>
              {file
                ? `${(file.size / 1024).toFixed(1)} KB · ${file.type}`
                : "or choose an image from your device"}
            </p>
            <input
              ref={input}
              className="sr-only"
              type="file"
              accept="image/jpeg,image/png"
              aria-label="Receipt image"
              disabled={busy}
              onChange={(e) => select(e.target.files[0])}
            />
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => input.current.click()}
            >
              {file ? "Choose another image" : "Choose file"}
            </button>
            <small>JPEG or PNG · up to 5 MB (5,242,880 bytes)</small>
          </div>
          {demo && (
            <label className="demo-outcome">
              Demonstration outcome
              <select
                aria-label="Demonstration outcome"
                value={outcome}
                disabled={busy}
                onChange={(e) => setOutcome(e.target.value)}
              >
                <option value="success">Simulate successful extraction</option>
                <option value="failure">Simulate extraction failure</option>
              </select>
              <small>
                Simulated results only. This does not scan your image or contact
                AWS.
              </small>
            </label>
          )}
          <button
            className="button primary upload-submit"
            onClick={start}
            disabled={!file || busy || phase === "completed"}
          >
            <Icon name="receipt" />
            {busy
              ? "Working…"
              : demo
                ? "Simulate receipt upload"
                : "Upload receipt"}
          </button>
          {phase !== "idle" && (
            <div className="processing-card" aria-live="polite">
              <div className="split">
                <h3>
                  {
                    {
                      uploading: "Uploading image",
                      processing: "Reading your receipt",
                      completed: demo
                        ? "Demo receipt completed"
                        : "Expense ready to review",
                      failed: "Receipt could not be processed",
                      waiting: "Processing is not confirmed",
                      error: "We couldn’t complete that step",
                    }[phase]
                  }
                </h3>
                {item && <Status value={item.status} />}
              </div>
              {phase === "uploading" && (
                <>
                  <progress
                    max={100}
                    value={progress}
                    aria-label="Receipt upload progress"
                  />
                  <p>
                    {progress}% uploaded. Extraction has not yet been confirmed.
                  </p>
                </>
              )}
              {phase === "processing" && (
                <p>
                  The image was sent. Waiting for a completed or failed
                  processing result…
                </p>
              )}
              {phase === "completed" && (
                <>
                  <p>
                    <strong>{item.merchant}</strong> · {money(item.total)}
                  </p>
                  <p>
                    Review the merchant, date and amount before relying on the
                    extracted details.
                  </p>
                  <Link className="text-link" to="/expenses">
                    Review expenses <Icon name="arrow" size={16} />
                  </Link>
                </>
              )}
              {phase === "failed" && (
                <>
                  <p className="negative">
                    {item.errorMessage ||
                      "Required receipt fields could not be extracted."}
                  </p>
                  <p>
                    {item.retryable
                      ? "The service may retry automatically. If this persists, ask the operator to replay the original receipt event."
                      : "Choose a clearer, corrected photo and upload again. An identical file may be detected as a duplicate."}
                  </p>
                </>
              )}
              {phase === "waiting" && (
                <p>
                  Polling stopped without a final result. The receipt may still
                  be processing. You can check its status again; no new upload
                  is needed.
                </p>
              )}
              {phase === "error" && item && (
                <p>
                  A receipt record exists. Check its status before submitting
                  the same file again.
                </p>
              )}
              {item && !busy && phase !== "completed" && (
                <button className="button secondary" onClick={refresh}>
                  Check receipt status
                </button>
              )}
              {busy && (
                <button className="text-button" onClick={cancel}>
                  Stop waiting
                </button>
              )}
            </div>
          )}
        </section>
        <aside className="receipt-guide">
          <section className="panel">
            <h2>A good photo goes a long way.</h2>
            <ol className="step-list">
              <li>
                <span>01</span>
                <div>
                  <h3>Keep it complete</h3>
                  <p>Include the merchant, transaction date and total.</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <h3>Let there be light</h3>
                  <p>Lay the receipt flat. Avoid shadows, glare and blur.</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <h3>Give it a quick review</h3>
                  <p>
                    Check the extracted details. You can edit completed
                    expenses.
                  </p>
                </div>
              </li>
            </ol>
          </section>
          <div className="privacy-note">
            <Icon name="shield" size={25} />
            <h3>Your receipts stay yours.</h3>
            <p>
              {demo
                ? "Demo files stay in your browser session. We simulate the workflow without sending your image anywhere."
                : "Uploads go directly to private receipt storage. Only your signed-in account can request access through the app."}
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
