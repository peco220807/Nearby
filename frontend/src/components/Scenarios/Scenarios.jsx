import { useState } from "react";
import { calculateScenarios } from "../../api.js";
import { parseCents, formatMoney } from "../../money.js";
import { Info } from "../icons.jsx";

// Defaults are only placeholders for the inputs; all math happens on the backend
const DEFAULT_FORM = { savings: "", income: "", hourly: "30", hours: "20", includeDisabled: false };

function parseHours(input) {
  const s = String(input).trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null;
  const h = Number(s);
  return h <= 168 ? h : null;
}

/** Form -> request body. Blank rate/hours are not sent, so the backend uses its defaults. */
export function buildRequest(form) {
  const savings = parseCents(form.savings);
  const income = parseCents(form.income);
  if (savings === null) return { error: "Savings: please enter a dollar amount, such as 100000 or 0." };
  if (income === null) return { error: "Monthly income: please enter a dollar amount, such as 2000 or 0." };
  const body = { savings_cents: savings, monthly_income_cents: income, include_disabled: form.includeDisabled };
  if (form.hourly.trim() !== "") {
    const hourly = parseCents(form.hourly);
    if (hourly === null) return { error: "Hourly rate: please enter a dollar amount, such as 30." };
    body.home_care_hourly_cents = hourly;
  }
  if (form.hours.trim() !== "") {
    const hours = parseHours(form.hours);
    if (hours === null) return { error: "Hours per week: a number from 0 to 168, with up to two decimals." };
    body.home_care_hours_per_week = hours;
  }
  return { body };
}

/** Display text for the months value; the numbers come from the API as-is */
export function monthsLabel(s) {
  if (s.months_covered === null) return "No gap";
  if (s.months_covered === 0) return "Less than 1 month";
  return `${s.months_covered} month${s.months_covered === 1 ? "" : "s"}`;
}

/** Source caption from the machine `kind` value returned by the API */
export function kindLabel(s) {
  if (s.kind === "survey") return `Survey data: ${s.source_name}`;
  if (s.kind === "user_estimate") return "Your estimate";
  return "Needs verification";
}

/** Bar width in percent of the longest finite scenario. Visualization only, no new numbers. */
export function barPercent(s, scenarios) {
  const finite = scenarios.map((x) => x.months_covered).filter((m) => m !== null);
  const max = finite.length ? Math.max(...finite) : 0;
  if (s.months_covered === null) return 100;
  if (max === 0) return 0;
  return Math.min(100, (s.months_covered / max) * 100);
}

export default function Scenarios() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function onSubmit(e) {
    e.preventDefault();
    const { body, error: err } = buildRequest(form);
    setError(err ?? null);
    if (err) return;
    setBusy(true);
    try {
      setResult(await calculateScenarios(body));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h1>How long could savings last?</h1>
      <p className="lead">
        Caring for a parent often means asking hard money questions. This page shows how long savings could last, one
        scenario at a time.
      </p>

      <form onSubmit={onSubmit} className="card">
        <div className="card-grid card-grid-2">
          <label className="field">
            Your parent's savings, $
            <input value={form.savings} onChange={set("savings")} inputMode="decimal" placeholder="e.g., 100000" required />
          </label>
          <label className="field">
            Your parent's monthly income, $ <span className="field-help">(Social Security, pension)</span>
            <input value={form.income} onChange={set("income")} inputMode="decimal" placeholder="e.g., 2000" required />
          </label>
        </div>
        <fieldset className="fieldset">
          <legend>If a hired aide helps at home</legend>
          <div className="card-grid card-grid-2">
            <label className="field">
              Hourly rate, $/hour
              <input value={form.hourly} onChange={set("hourly")} inputMode="decimal" placeholder="30" />
            </label>
            <label className="field">
              Hours per week
              <input value={form.hours} onChange={set("hours")} inputMode="decimal" placeholder="20" />
            </label>
          </div>
        </fieldset>
        <label className="check">
          <input type="checkbox" checked={form.includeDisabled} onChange={set("includeDisabled")} />
          <span>Also show memory care. Its source still needs verification, so it's off by default.</span>
        </label>
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        <div className="action-bar">
          <button type="submit" className="btn btn-accent" disabled={busy}>
            {busy ? "Working it out…" : "See how long savings last"}
          </button>
        </div>
      </form>

      {!result && <p className="empty">Nothing to show yet. Enter savings to see your estimate.</p>}

      {result && (
        <>
          <h2>Here's the picture</h2>
          <p className="lead">Numbers can feel overwhelming. Take them one scenario at a time. The longest bar is the option where savings last longest.</p>
          {result.scenarios.map((s) => (
            <article key={s.id} className="card scenario">
              <div className="scenario-head">
                <h3>{s.name}</h3>
                <span className="scenario-months">{monthsLabel(s)}</span>
              </div>
              <div className="bar-track" role="img" aria-label={`${s.name}: ${s.status}`}>
                <div
                  className={`bar-fill${s.months_covered === null ? " bar-nogap" : ""}`}
                  style={{ width: `${barPercent(s, result.scenarios)}%` }}
                />
              </div>
              <div className="scenario-facts">
                <span>
                  Monthly cost <b>{formatMoney(s.monthly_cost_cents)}</b>
                </span>
                <span>
                  Monthly gap <b>{s.monthly_gap_cents === 0 ? "none" : formatMoney(s.monthly_gap_cents)}</b>
                </span>
                <span>{s.status}</span>
              </div>
              <p className="scenario-source">
                {kindLabel(s)}
                {s.as_of && s.kind !== "survey" && `, ${s.as_of} data`}
                {s.hourly_cents != null && ` · ${formatMoney(s.hourly_cents)}/hour × ${s.hours_per_week} hours/week`}
                {s.source_url && (
                  <>
                    {" · "}
                    <a href={s.source_url} target="_blank" rel="noopener noreferrer">
                      source
                    </a>
                  </>
                )}
              </p>
            </article>
          ))}
          <p className="notice">
            This is a starting point, not a decision. Many families talk these options through with a social worker or
            elder-care advisor.
          </p>
          <details className="card">
            <summary>Still have questions? Where these numbers come from</summary>
            <ul>
              {result.scenarios.map((s) => (
                <li key={s.id}>
                  <strong>{s.name}:</strong> {s.note}
                </li>
              ))}
            </ul>
          </details>
          <p className="disclaimer">
            <Info />
            <span>{result.disclaimer}</span>
          </p>
        </>
      )}
    </section>
  );
}
