import { useState } from "react";
import { screenEligibility } from "../../api.js";
import { EMPTY_FORM, STATES, STATUS_LABELS, YES_NO_STEPS, buildAnswers, formatDate, resultToText, validateStep } from "./answers.js";
import { Info } from "../icons.jsx";

const STEPS = 5;
const STEP_TITLES = {
  1: "Where your parent lives",
  2: "Military service and family",
  3: "Your parent's health and coverage",
  4: "Income and assets",
  5: "About you, the caregiver",
};
const PILL_CLASS = { possible: "pill-possible", "needs review": "pill-review", unlikely: "pill-unlikely" };

export function StatusPill({ status }) {
  return <span className={`pill ${PILL_CLASS[status] ?? "pill-review"}`}>{STATUS_LABELS[status] ?? status}</span>;
}

export default function Eligibility() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(null);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function next(e) {
    e.preventDefault();
    const err = validateStep(step, form);
    setError(err);
    if (err) return;
    if (step < STEPS) {
      setStep(step + 1);
      window.scrollTo({ top: 0 });
      return;
    }
    setBusy(true);
    try {
      setResult(await screenEligibility(buildAnswers(form)));
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    setForm(EMPTY_FORM);
    setResult(null);
    setStep(1);
    setError(null);
    setCopied(null);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(resultToText(result));
      setCopied("Results copied to the clipboard.");
    } catch {
      setCopied("Could not copy automatically. Please select the text and copy it by hand.");
    }
  }

  if (result) {
    return (
      <section>
        <h1>Here's what might apply</h1>
        <p className="lead">
          This can be a lot to take in, so go one program at a time. Each shows one of three statuses. None of them is a
          decision: the program itself decides.
        </p>
        <div className="legend" aria-hidden="true">
          <StatusPill status="possible" />
          <StatusPill status="needs review" />
          <StatusPill status="unlikely" />
        </div>
        {result.programs.map((p) => (
          <ProgramCard key={p.id} program={p} />
        ))}
        <p className="notice">
          This is a starting point, not a decision. If something looks possible, the primary source is the place to check
          the details, and a benefits counselor or social worker can help with the application.
        </p>
        <div className="action-bar">
          <button type="button" className="btn" onClick={copy}>
            Copy results
          </button>
          <button type="button" className="btn btn-secondary" onClick={restart}>
            Start over
          </button>
        </div>
        {copied && (
          <p role="status" className="notice">
            {copied}
          </p>
        )}
        <p className="disclaimer">
          <Info />
          <span>{result.disclaimer}</span>
        </p>
      </section>
    );
  }

  return (
    <section>
      <h1>Benefits check</h1>
      <p className="lead">
        Many families never learn about help they may qualify for. Answer a few questions, and we'll show what might apply.
        Every question is optional, and nothing is saved.
      </p>
      <div className="card">
        <div className="steps" aria-label={`Step ${step} of ${STEPS}`}>
          <p className="steps-label">
            Step {step} of {STEPS}
          </p>
          <div className="steps-track" aria-hidden="true">
            {Array.from({ length: STEPS }, (_, i) => (
              <span key={i} className={i < step ? "done" : ""} />
            ))}
          </div>
        </div>
        <h2>{STEP_TITLES[step]}</h2>
        {step !== 5 && <p className="hint">Not sure about something? That's fine. Leave "Not sure" and we'll mark it for review.</p>}
        {step === 5 && <p className="hint">These last questions are about you, not your parent. They matter for the Dependent Care Credit.</p>}
        <form onSubmit={next}>
          {step === 1 && (
            <>
              <label className="field">
                State
                <select value={form.state} onChange={set("state")}>
                  <option value="">Not selected</option>
                  {STATES.map(([code, name]) => (
                    <option key={code} value={code}>
                      {name} ({code})
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Your parent's age
                <input value={form.age} onChange={set("age")} inputMode="numeric" placeholder="e.g., 82" />
              </label>
            </>
          )}

          {YES_NO_STEPS[step] &&
            YES_NO_STEPS[step].map(([key, question]) => (
              <fieldset key={key} className="question">
                <legend>{question}</legend>
                <div className="choices">
                  {[["yes", "Yes"], ["no", "No"], ["unknown", "Not sure"]].map(([value, label]) => (
                    <label key={value} className="choice">
                      <input type="radio" name={key} value={value} checked={form[key] === value} onChange={set(key)} />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}

          {step === 4 && (
            <>
              <label className="field">
                Your parent's annual income, $
                <input value={form.income} onChange={set("income")} inputMode="decimal" placeholder="e.g., 15000" />
              </label>
              <label className="field">
                Your parent's net worth, $ <span className="field-help">(excluding the home and car, minus debts)</span>
                <input value={form.netWorth} onChange={set("netWorth")} inputMode="decimal" placeholder="e.g., 50000" />
              </label>
            </>
          )}

          {error && (
            <p role="alert" className="alert">
              {error}
            </p>
          )}

          <div className="action-bar">
            {step > 1 && (
              <button type="button" className="btn btn-secondary" onClick={() => setStep(step - 1)}>
                Back
              </button>
            )}
            <button type="submit" className="btn btn-accent" disabled={busy}>
              {step < STEPS ? "Next" : busy ? "Checking…" : "See results"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function ProgramCard({ program: p }) {
  return (
    <article className="card">
      <header className="card-head">
        <h3>{p.name}</h3>
        <StatusPill status={p.status} />
      </header>
      <p>{p.result_description}</p>

      {p.reasons.length > 0 && <List title="Why it's unlikely" items={p.reasons} />}
      {p.to_check.length > 0 && <List title="Worth checking" items={p.to_check} />}
      {p.documents.length > 0 && <List title="Documents you'd need" items={p.documents} />}

      <p style={{ marginTop: 14 }}>
        <a href={p.source_url} target="_blank" rel="noopener noreferrer">
          Primary source ↗
        </a>
      </p>
      {p.amounts_source_urls.length > 0 && (
        <div>
          <h4>Sources for the amounts</h4>
          <ul>
            {p.amounts_source_urls.map((url) => (
              <li key={url}>
                <a href={url} target="_blank" rel="noopener noreferrer">
                  {url.replace(/^https:\/\//, "")}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="meta">
        Still have questions? The primary source above has the full rules. We last checked them on {formatDate(p.last_verified)}.
        {p.amounts_valid_until && (
          <>
            <br />
            <strong>Amounts valid until: {formatDate(p.amounts_valid_until)}</strong>
          </>
        )}
        {p.amounts_note && (
          <>
            <br />
            Amounts: {p.amounts_note}
          </>
        )}
      </p>
    </article>
  );
}

function List({ title, items }) {
  return (
    <div>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
