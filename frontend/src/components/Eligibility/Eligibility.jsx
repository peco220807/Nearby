import { useState } from "react";
import { screenEligibility } from "../../api.js";
import { EMPTY_FORM, STATES, YES_NO_STEPS, buildAnswers, formatDate, resultToText, validateStep } from "./answers.js";
import "./Eligibility.css";

const STEPS = 5;
const STEP_TITLES = {
  1: "Где живёт родитель",
  2: "Военная служба и семья",
  3: "Состояние родителя",
  4: "Доход и активы",
  5: "О том, кто помогает родителю",
};
const BADGE = { "возможно": "possible", "нужна проверка": "check", "скорее не подходит": "unlikely" };

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
      return;
    }
    setBusy(true);
    try {
      setResult(await screenEligibility(buildAnswers(form)));
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
      setCopied("Результат скопирован.");
    } catch {
      setCopied("Не удалось скопировать. Выделите текст вручную.");
    }
  }

  if (result) {
    return (
      <section className="elig">
        <h2>Результаты скрининга</h2>
        {result.programs.map((p) => (
          <ProgramCard key={p.id} program={p} />
        ))}
        <div className="elig-actions">
          <button type="button" className="elig-btn" onClick={copy}>
            Скопировать результат
          </button>
          <button type="button" className="elig-btn elig-btn-secondary" onClick={restart}>
            Пройти заново
          </button>
        </div>
        {copied && <p role="status">{copied}</p>}
        <p className="elig-disclaimer">{result.disclaimer}</p>
      </section>
    );
  }

  return (
    <section className="elig">
      <h2>Льготы для родителя</h2>
      <p className="elig-progress">
        Шаг {step} из {STEPS}: {STEP_TITLES[step]}
      </p>
      <p className="elig-hint">Все вопросы необязательные. Если не знаете ответ, оставьте «Не знаю».</p>
      <form onSubmit={next}>
        {step === 1 && (
          <>
            <label className="elig-field">
              Штат
              <select value={form.state} onChange={set("state")}>
                <option value="">Не выбран</option>
                {STATES.map(([code, name]) => (
                  <option key={code} value={code}>
                    {name} ({code})
                  </option>
                ))}
              </select>
            </label>
            <label className="elig-field">
              Возраст родителя
              <input value={form.age} onChange={set("age")} inputMode="numeric" placeholder="например, 82" />
            </label>
          </>
        )}

        {step === 5 && <p className="elig-hint">Эти вопросы — про вас, а не про родителя. Они нужны для налогового кредита.</p>}

        {YES_NO_STEPS[step] &&
          YES_NO_STEPS[step].map(([key, question]) => (
            <fieldset key={key} className="elig-question">
              <legend>{question}</legend>
              {[["yes", "Да"], ["no", "Нет"], ["unknown", "Не знаю"]].map(([value, label]) => (
                <label key={value} className="elig-choice">
                  <input type="radio" name={key} value={value} checked={form[key] === value} onChange={set(key)} />
                  {label}
                </label>
              ))}
            </fieldset>
          ))}

        {step === 4 && (
          <>
            <label className="elig-field">
              Годовой доход родителя, $
              <input value={form.income} onChange={set("income")} inputMode="decimal" placeholder="например, 15000" />
            </label>
            <label className="elig-field">
              Чистые активы родителя, $ (без дома и машины, за вычетом долгов)
              <input value={form.netWorth} onChange={set("netWorth")} inputMode="decimal" placeholder="например, 50000" />
            </label>
          </>
        )}

        {error && (
          <p role="alert" className="elig-error">
            {error}
          </p>
        )}

        <div className="elig-actions">
          {step > 1 && (
            <button type="button" className="elig-btn elig-btn-secondary" onClick={() => setStep(step - 1)}>
              Назад
            </button>
          )}
          <button type="submit" className="elig-btn" disabled={busy}>
            {step < STEPS ? "Далее" : busy ? "Проверяем…" : "Показать результат"}
          </button>
        </div>
      </form>
    </section>
  );
}

function ProgramCard({ program: p }) {
  return (
    <article className="elig-card">
      <header className="elig-card-head">
        <h3>{p.name}</h3>
        <span className={`elig-badge elig-badge-${BADGE[p.status] ?? "check"}`}>{p.status}</span>
      </header>
      <p>{p.result_description}</p>

      {p.reasons.length > 0 && <List title="Что говорит против" items={p.reasons} />}
      {p.to_check.length > 0 && <List title="Что проверить" items={p.to_check} />}
      {p.documents.length > 0 && <List title="Документы" items={p.documents} />}

      <p>
        <a href={p.source_url} target="_blank" rel="noopener noreferrer">
          Первичный источник
        </a>
      </p>
      {p.amounts_source_urls.length > 0 && (
        <div>
          <h4>Источники сумм</h4>
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
      <p className="elig-meta">
        Правила проверены: {formatDate(p.last_verified)}
        {p.amounts_valid_until && (
          <>
            <br />
            <strong>Суммы действуют до: {formatDate(p.amounts_valid_until)}</strong>
          </>
        )}
        {p.amounts_note && (
          <>
            <br />
            Суммы: {p.amounts_note}
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
