import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getHousehold, getBalance, addExpense, addHelpHours } from "../api.js";
import { parseCents, formatMoney } from "../money.js";
import Layout from "../components/Layout.jsx";
import { ArrowRight } from "../components/icons.jsx";

const TABS = { balance: "Who's helping", expense: "Add expense", help: "Log help hours" };
const CATEGORIES = { medication: "Medication", care: "Care", transport: "Transport", other: "Other" };

// Local date for the user (toISOString would give the UTC date)
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// Same rule as the backend: 0 < hours <= 24, at most two decimals
function parseHours(input) {
  const s = String(input).trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null;
  const h = Number(s);
  return h > 0 && h <= 24 ? h : null;
}

export default function Family() {
  const { token } = useParams();
  const [household, setHousehold] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("balance");

  useEffect(() => {
    getHousehold(token).then(setHousehold, (err) => setError(err.message));
  }, [token]);

  return (
    <Layout wide>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!error && !household && <p>Loading…</p>}
      {household && (
        <>
          <h1>{household.name}</h1>
          <p className="lead">
            Caring for {household.parent_name || "a parent"} is shared work. Track who's helping, and what it costs.
          </p>
          <div className="share-box">
            <span>Your family's private link. Anyone with it can add to this ledger:</span>
            <code>{window.location.href}</code>
          </div>
          <div className="tabs" role="tablist" aria-label="Ledger sections">
            {Object.entries(TABS).map(([key, label]) => (
              <button key={key} type="button" role="tab" className="tab" aria-selected={tab === key} onClick={() => setTab(key)}>
                {label}
              </button>
            ))}
          </div>
          {tab === "balance" && <BalanceTab token={token} members={household.members} />}
          {tab === "expense" && <ExpenseTab token={token} members={household.members} />}
          {tab === "help" && <HelpTab token={token} members={household.members} />}
        </>
      )}
    </Layout>
  );
}

function netText(net) {
  if (net > 0) return { cls: "owed", text: `is owed ${formatMoney(net)}` };
  if (net < 0) return { cls: "owes", text: `owes ${formatMoney(-net)}` };
  return { cls: "even", text: "settled up" };
}

function BalanceTab({ token, members }) {
  const [balance, setBalance] = useState(null);
  const [error, setError] = useState(null);
  const names = Object.fromEntries(members.map((m) => [m.id, m.name]));

  useEffect(() => {
    getBalance(token).then(setBalance, (err) => setError(err.message));
  }, [token]);

  if (error)
    return (
      <p role="alert" className="alert">
        {error}
      </p>
    );
  if (!balance) return <p>Loading…</p>;

  const help = Object.entries(balance.help_share_percent).sort((a, b) => b[1] - a[1]);
  const topHelper = help.find(([, pct]) => pct > 0);

  return (
    <section>
      <h2>Who's helping</h2>
      <p className="hint">Everyone's share so far, in money and in time.</p>
      <div className="card-grid card-grid-3" style={{ marginBottom: 16 }}>
        {balance.members.map((b) => {
          const net = netText(b.net_cents);
          return (
            <article key={b.member_id} className="card member" style={{ marginBottom: 0 }}>
              <span className="member-name">{b.name}</span>
              <span className={`member-net ${net.cls}`}>{net.text}</span>
              <span className="member-row">
                Paid <b>{formatMoney(b.paid_cents)}</b>
              </span>
              <span className="member-row">
                Share of expenses <b>{formatMoney(b.owed_cents)}</b>
              </span>
            </article>
          );
        })}
      </div>

      <div className="card-grid card-grid-2">
        <div className="card">
          <h3>To even things out</h3>
          <p className="hint">The fewest transfers that bring everyone to the same share.</p>
          {balance.transfers.length === 0 ? (
            <p className="muted">Everyone's even. Nothing to settle right now.</p>
          ) : (
            <div>
              {balance.transfers.map((t, i) => (
                <div key={i} className="transfer">
                  <strong>{names[t.from_id]}</strong> pays <ArrowRight /> <strong>{names[t.to_id]}</strong>
                  <span className="amount">{formatMoney(t.amount_cents)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3>Time given</h3>
          {help.length === 0 ? (
            <p className="muted">No hours logged yet. When someone helps, log it here. It counts.</p>
          ) : (
            <div>
              {topHelper && (
                <p className="ack">
                  {names[topHelper[0]]} has covered {topHelper[1]}% of the help hours logged so far. Thank you.
                </p>
              )}
              {help.map(([id, pct]) => (
                <div key={id} className="transfer">
                  <strong>{names[id]}</strong>
                  <span className="amount">{pct}%</span>
                </div>
              ))}
              <p className="hint" style={{ marginTop: 8 }}>
                Each person's share of all the help hours the family has logged.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function StatusLine({ status }) {
  if (!status) return null;
  return (
    <p role={status.error ? "alert" : "status"} className={status.error ? "alert" : "notice"}>
      {status.text}
    </p>
  );
}

function ExpenseTab({ token, members }) {
  const empty = { paidBy: String(members[0]?.id ?? ""), amount: "", category: "medication", description: "", date: today() };
  const [form, setForm] = useState(empty);
  const [status, setStatus] = useState(null);
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function onSubmit(e) {
    e.preventDefault();
    const cents = parseCents(form.amount);
    if (!cents) {
      setStatus({ error: true, text: "Amount must be greater than zero, with at most two decimals." });
      return;
    }
    try {
      await addExpense(token, {
        paid_by_id: Number(form.paidBy),
        amount_cents: cents,
        category: form.category,
        description: form.description.trim() || null,
        expense_date: form.date,
      });
      setForm({ ...empty, paidBy: form.paidBy });
      setStatus({ error: false, text: `Added ${formatMoney(cents)}. It's split equally, so everyone's share is updated.` });
    } catch (err) {
      setStatus({ error: true, text: err.message });
    }
  }

  return (
    <form onSubmit={onSubmit} className="card">
      <h2>Add an expense</h2>
      <div className="card-grid card-grid-2">
        <label className="field">
          Who paid
          <select value={form.paidBy} onChange={set("paidBy")}>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Amount, $
          <input value={form.amount} onChange={set("amount")} inputMode="decimal" placeholder="e.g., 12.50" required />
        </label>
        <label className="field">
          Category
          <select value={form.category} onChange={set("category")}>
            {Object.entries(CATEGORIES).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Date
          <input type="date" value={form.date} onChange={set("date")} required />
        </label>
      </div>
      <label className="field">
        Description <span className="field-help">(optional)</span>
        <input value={form.description} onChange={set("description")} maxLength={200} />
      </label>
      <p className="hint">Split equally between everyone, so no one carries it alone.</p>
      <StatusLine status={status} />
      <div className="action-bar">
        <button type="submit" className="btn btn-accent">
          Add expense
        </button>
      </div>
    </form>
  );
}

function HelpTab({ token, members }) {
  const empty = { member: String(members[0]?.id ?? ""), hours: "", date: today(), note: "" };
  const [form, setForm] = useState(empty);
  const [status, setStatus] = useState(null);
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function onSubmit(e) {
    e.preventDefault();
    const hours = parseHours(form.hours);
    if (hours === null) {
      setStatus({ error: true, text: "Hours must be greater than 0 and at most 24, with up to two decimals." });
      return;
    }
    try {
      await addHelpHours(token, {
        member_id: Number(form.member),
        hours,
        entry_date: form.date,
        note: form.note.trim() || null,
      });
      setForm({ ...empty, member: form.member });
      setStatus({ error: false, text: `Logged ${hours} hour${hours === 1 ? "" : "s"}. Thank you for the time you give.` });
    } catch (err) {
      setStatus({ error: true, text: err.message });
    }
  }

  return (
    <form onSubmit={onSubmit} className="card">
      <h2>Log help hours</h2>
      <p className="hint">Time counts too. Hours go toward each person's share of the load, not toward money.</p>
      <div className="card-grid card-grid-2">
        <label className="field">
          Who helped
          <select value={form.member} onChange={set("member")}>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Hours
          <input type="number" value={form.hours} onChange={set("hours")} min="0.01" max="24" step="0.01" required />
        </label>
        <label className="field">
          Date
          <input type="date" value={form.date} onChange={set("date")} required />
        </label>
        <label className="field">
          Note <span className="field-help">(optional)</span>
          <input value={form.note} onChange={set("note")} maxLength={200} />
        </label>
      </div>
      <StatusLine status={status} />
      <div className="action-bar">
        <button type="submit" className="btn btn-accent">
          Log hours
        </button>
      </div>
    </form>
  );
}
