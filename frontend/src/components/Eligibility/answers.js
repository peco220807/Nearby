// Чистые функции опроса: без React, чтобы их можно было проверить отдельно.
import { parseCents } from "../../money.js";

export const STATES = [
  ["AL", "Алабама"], ["AK", "Аляска"], ["AZ", "Аризона"], ["AR", "Арканзас"], ["CA", "Калифорния"],
  ["CO", "Колорадо"], ["CT", "Коннектикут"], ["DE", "Делавэр"], ["DC", "Округ Колумбия"], ["FL", "Флорида"],
  ["GA", "Джорджия"], ["HI", "Гавайи"], ["ID", "Айдахо"], ["IL", "Иллинойс"], ["IN", "Индиана"],
  ["IA", "Айова"], ["KS", "Канзас"], ["KY", "Кентукки"], ["LA", "Луизиана"], ["ME", "Мэн"],
  ["MD", "Мэриленд"], ["MA", "Массачусетс"], ["MI", "Мичиган"], ["MN", "Миннесота"], ["MS", "Миссисипи"],
  ["MO", "Миссури"], ["MT", "Монтана"], ["NE", "Небраска"], ["NV", "Невада"], ["NH", "Нью-Гэмпшир"],
  ["NJ", "Нью-Джерси"], ["NM", "Нью-Мексико"], ["NY", "Нью-Йорк"], ["NC", "Северная Каролина"],
  ["ND", "Северная Дакота"], ["OH", "Огайо"], ["OK", "Оклахома"], ["OR", "Орегон"], ["PA", "Пенсильвания"],
  ["RI", "Род-Айленд"], ["SC", "Южная Каролина"], ["SD", "Южная Дакота"], ["TN", "Теннесси"], ["TX", "Техас"],
  ["UT", "Юта"], ["VT", "Вермонт"], ["VA", "Вирджиния"], ["WA", "Вашингтон"], ["WV", "Западная Вирджиния"],
  ["WI", "Висконсин"], ["WY", "Вайоминг"],
].sort((a, b) => a[1].localeCompare(b[1], "ru"));

// Вопросы «да / нет / не знаю» по шагам. key — поле ScreeningAnswers на бэкенде.
export const YES_NO_STEPS = {
  2: [
    ["is_veteran", "Родитель — ветеран?"],
    ["is_surviving_spouse_of_veteran", "Родитель — вдова или вдовец ветерана?"],
    ["wartime_service", "Служба (родителя или его супруга-ветерана) была в военное время?"],
    ["has_spouse", "Родитель состоит в браке?"],
    ["va_service_rating_70_plus", "Если родитель — ветеран: рейтинг нарушения здоровья VA, связанного со службой, 70% или выше?"],
  ],
  3: [
    ["needs_help_daily_activities", "Нужна ли родителю помощь в повседневных делах (мытьё, еда, одевание)?"],
    ["in_nursing_home", "Родитель живёт в доме престарелых?"],
    ["has_medicare", "У родителя есть Medicare?"],
  ],
  // Шаг 5 — про того, кто помогает родителю (налоговый кредит на уход за иждивенцем)
  5: [
    ["lives_with_caregiver_over_half_year", "Родитель жил с вами больше половины года?"],
    ["caregiver_provides_over_half_support", "Вы обеспечиваете больше 50% всей поддержки родителя за год (жильё, еда, лечение)?"],
    ["caregiver_works", "Вы работаете или ищете работу, и уход за родителем нужен, чтобы вы могли работать?"],
  ],
};

export const EMPTY_FORM = {
  state: "",
  age: "",
  income: "",
  netWorth: "",
  ...Object.fromEntries(Object.values(YES_NO_STEPS).flat().map(([key]) => [key, "unknown"])),
};

const TRI = { yes: true, no: false, unknown: null };

/** "2026-11-30" → "30.11.2026" */
export const formatDate = (iso) => iso.split("-").reverse().join(".");

/** Проверка шага: возвращает текст ошибки или null. */
export function validateStep(step, form) {
  if (step === 1 && form.age.trim() !== "") {
    const age = Number(form.age);
    if (!Number.isInteger(age) || age < 0 || age > 130) return "Возраст — целое число от 0 до 130 или пусто.";
  }
  if (step === 4) {
    for (const [field, label] of [["income", "Годовой доход"], ["netWorth", "Чистые активы"]]) {
      if (form[field].trim() !== "" && parseCents(form[field]) === null) {
        return `${label}: введите сумму в долларах, например 15000 или 15000.50, или оставьте пустым.`;
      }
    }
  }
  return null;
}

/** Форма → тело запроса. «Не знаю» и пустые поля → null (не false и не 0). */
export function buildAnswers(form) {
  const money = (v) => (v.trim() === "" ? null : parseCents(v));
  const answers = {
    state: form.state || null,
    age: form.age.trim() === "" ? null : Number(form.age),
    annual_income_cents: money(form.income),
    net_worth_cents: money(form.netWorth),
  };
  for (const [key] of Object.values(YES_NO_STEPS).flat()) answers[key] = TRI[form[key]];
  return answers;
}

/** Результат → простой текст для копирования. Только тексты из ответа API. */
export function resultToText(result) {
  const lines = ["Скрининг льгот для родителя (предварительный)", ""];
  for (const p of result.programs) {
    lines.push(`${p.name} — ${p.status}`, p.result_description);
    if (p.reasons.length) lines.push("Что говорит против:", ...p.reasons.map((r) => `- ${r}`));
    if (p.to_check.length) lines.push("Что проверить:", ...p.to_check.map((r) => `- ${r}`));
    if (p.documents.length) lines.push("Документы:", ...p.documents.map((r) => `- ${r}`));
    lines.push(`Первичный источник: ${p.source_url}`);
    for (const url of p.amounts_source_urls) lines.push(`Источник сумм: ${url}`);
    if (p.amounts_valid_until) lines.push(`Суммы действуют до: ${formatDate(p.amounts_valid_until)}`);
    if (p.amounts_note) lines.push(`Суммы: ${p.amounts_note}`);
    lines.push(`Дата проверки правил: ${formatDate(p.last_verified)}`, "");
  }
  lines.push(result.disclaimer);
  return lines.join("\n");
}
