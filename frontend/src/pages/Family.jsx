import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getHousehold, getBalance, addExpense, addHelpHours } from "../api.js";
import { parseCents, formatCents } from "../money.js";

const TABS = { balance: "Баланс", expense: "Расход", help: "Часы помощи родителю" };
const CATEGORIES = { medication: "Лекарства", care: "Уход", transport: "Транспорт", other: "Другое" };
// Локальная дата пользователя (toISOString дал бы дату по UTC)
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// Как на бэкенде: 0 < часы <= 24; не больше двух знаков после запятой
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

  if (error) return <p role="alert">Ошибка: {error}</p>;
  if (!household) return <p>Загрузка…</p>;

  return (
    <main>
      <p>
        <Link to="/">← На главную</Link>
      </p>
      <h1>{household.name}</h1>
      {household.parent_name && <p>Родитель: {household.parent_name}</p>}
      <p>
        Ссылка для семьи: <code>{window.location.href}</code>
      </p>
      <nav>
        {Object.entries(TABS).map(([key, label]) => (
          <button key={key} type="button" onClick={() => setTab(key)} disabled={tab === key}>
            {label}
          </button>
        ))}
      </nav>
      <hr />
      {tab === "balance" && <BalanceTab token={token} members={household.members} />}
      {tab === "expense" && <ExpenseTab token={token} members={household.members} />}
      {tab === "help" && <HelpTab token={token} members={household.members} />}
    </main>
  );
}

function BalanceTab({ token, members }) {
  const [balance, setBalance] = useState(null);
  const [error, setError] = useState(null);
  const names = Object.fromEntries(members.map((m) => [m.id, m.name]));

  useEffect(() => {
    getBalance(token).then(setBalance, (err) => setError(err.message));
  }, [token]);

  if (error) return <p role="alert">Ошибка: {error}</p>;
  if (!balance) return <p>Загрузка…</p>;

  const help = Object.entries(balance.help_share_percent);

  return (
    <section>
      <h2>Баланс</h2>
      <table>
        <thead>
          <tr>
            <th>Участник</th>
            <th>Заплатил</th>
            <th>Доля расходов</th>
            <th>Итог</th>
          </tr>
        </thead>
        <tbody>
          {balance.members.map((b) => (
            <tr key={b.member_id}>
              <td>{b.name}</td>
              <td>{formatCents(b.paid_cents)}</td>
              <td>{formatCents(b.owed_cents)}</td>
              <td>
                {b.net_cents > 0 && `+${formatCents(b.net_cents)} (ему должны)`}
                {b.net_cents < 0 && `${formatCents(b.net_cents)} (он должен)`}
                {b.net_cents === 0 && "0.00"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Переводы</h3>
      {balance.transfers.length === 0 ? (
        <p>Все в расчёте.</p>
      ) : (
        <ul>
          {balance.transfers.map((t, i) => (
            <li key={i}>
              {names[t.from_id]} → {names[t.to_id]}: {formatCents(t.amount_cents)}
            </li>
          ))}
        </ul>
      )}

      <h3>Часы помощи родителю</h3>
      {help.length === 0 ? (
        <p>Часов пока нет.</p>
      ) : (
        <ul>
          {help.map(([id, pct]) => (
            <li key={id}>
              {names[id]}: {pct}%
            </li>
          ))}
        </ul>
      )}
    </section>
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
      setStatus("Ошибка: сумма должна быть больше нуля, не больше двух знаков после точки");
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
      setStatus(`Расход ${formatCents(cents)} добавлен`);
    } catch (err) {
      setStatus(`Ошибка: ${err.message}`);
    }
  }

  return (
    <section>
      <h2>Новый расход</h2>
      <form onSubmit={onSubmit}>
        <p>
          <label>
            Кто заплатил{" "}
            <select value={form.paidBy} onChange={set("paidBy")}>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
        </p>
        <p>
          <label>
            Сумма <input value={form.amount} onChange={set("amount")} inputMode="decimal" placeholder="12.50" required />
          </label>
        </p>
        <p>
          <label>
            Категория{" "}
            <select value={form.category} onChange={set("category")}>
              {Object.entries(CATEGORIES).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </p>
        <p>
          <label>
            Описание <input value={form.description} onChange={set("description")} maxLength={200} />
          </label>
        </p>
        <p>
          <label>
            Дата <input type="date" value={form.date} onChange={set("date")} required />
          </label>
        </p>
        <p>Делится поровну между всеми участниками.</p>
        <button type="submit">Добавить</button>
        {status && <p role="status">{status}</p>}
      </form>
    </section>
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
      setStatus("Ошибка: часы должны быть больше 0 и не больше 24, до двух знаков после запятой");
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
      setStatus(`Записано ${hours} ч`);
    } catch (err) {
      setStatus(`Ошибка: ${err.message}`);
    }
  }

  return (
    <section>
      <h2>Часы помощи родителю</h2>
      <form onSubmit={onSubmit}>
        <p>
          <label>
            Кто помогал{" "}
            <select value={form.member} onChange={set("member")}>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
        </p>
        <p>
          <label>
            Часы{" "}
            <input type="number" value={form.hours} onChange={set("hours")} min="0.01" max="24" step="0.01" required />
          </label>
        </p>
        <p>
          <label>
            Дата <input type="date" value={form.date} onChange={set("date")} required />
          </label>
        </p>
        <p>
          <label>
            Заметка <input value={form.note} onChange={set("note")} maxLength={200} />
          </label>
        </p>
        <button type="submit">Записать</button>
        {status && <p role="status">{status}</p>}
      </form>
    </section>
  );
}
