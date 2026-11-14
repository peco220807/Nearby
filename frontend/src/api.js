const BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

async function request(path, options = {}) {
  const res = await fetch(BASE_URL + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join("; ")
          : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });
const enc = encodeURIComponent;

export const getHealth = () => request("/health");

// { name, parent_name, member_names: [] } -> { id, name, parent_name, share_token, members }
export const createHousehold = (data) => post("/households", data);

export const getHousehold = (token) => request(`/households/${enc(token)}`);

// { paid_by_id, amount_cents, category, description, expense_date }
export const addExpense = (token, data) => post(`/households/${enc(token)}/expenses`, data);

// { member_id, hours, entry_date, note }
export const addHelpHours = (token, data) => post(`/households/${enc(token)}/help-hours`, data);

// -> { members, transfers, help_share_percent }
export const getBalance = (token) => request(`/households/${enc(token)}/balance`);

// Survey answers (every field optional) -> { disclaimer, programs }
export const screenEligibility = (answers) => post("/eligibility/screen", answers);

// { savings_cents, monthly_income_cents, home_care_hourly_cents?, home_care_hours_per_week?, include_disabled? }
// -> { disclaimer, scenarios }
export const calculateScenarios = (body) => post("/scenarios/calculate", body);
