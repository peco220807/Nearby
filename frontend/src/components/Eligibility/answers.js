// Pure questionnaire helpers: no React, so they can be tested on their own.
import { parseCents } from "../../money.js";

export const STATES = [
  ["AL", "Alabama"], ["AK", "Alaska"], ["AZ", "Arizona"], ["AR", "Arkansas"], ["CA", "California"],
  ["CO", "Colorado"], ["CT", "Connecticut"], ["DE", "Delaware"], ["DC", "District of Columbia"], ["FL", "Florida"],
  ["GA", "Georgia"], ["HI", "Hawaii"], ["ID", "Idaho"], ["IL", "Illinois"], ["IN", "Indiana"],
  ["IA", "Iowa"], ["KS", "Kansas"], ["KY", "Kentucky"], ["LA", "Louisiana"], ["ME", "Maine"],
  ["MD", "Maryland"], ["MA", "Massachusetts"], ["MI", "Michigan"], ["MN", "Minnesota"], ["MS", "Mississippi"],
  ["MO", "Missouri"], ["MT", "Montana"], ["NE", "Nebraska"], ["NV", "Nevada"], ["NH", "New Hampshire"],
  ["NJ", "New Jersey"], ["NM", "New Mexico"], ["NY", "New York"], ["NC", "North Carolina"],
  ["ND", "North Dakota"], ["OH", "Ohio"], ["OK", "Oklahoma"], ["OR", "Oregon"], ["PA", "Pennsylvania"],
  ["RI", "Rhode Island"], ["SC", "South Carolina"], ["SD", "South Dakota"], ["TN", "Tennessee"], ["TX", "Texas"],
  ["UT", "Utah"], ["VT", "Vermont"], ["VA", "Virginia"], ["WA", "Washington"], ["WV", "West Virginia"],
  ["WI", "Wisconsin"], ["WY", "Wyoming"],
].sort((a, b) => a[1].localeCompare(b[1], "en"));

// Yes / No / Not sure questions by step. key = ScreeningAnswers field on the backend.
export const YES_NO_STEPS = {
  2: [
    ["is_veteran", "Is your parent a veteran?"],
    ["is_surviving_spouse_of_veteran", "Is your parent the surviving spouse of a veteran?"],
    ["wartime_service", "Did the veteran's service (your parent's, or their late spouse's) include a wartime period?"],
    ["has_spouse", "Is your parent married?"],
    ["va_service_rating_70_plus", "If your parent is a veteran: is their VA service-connected disability rating 70% or higher?"],
  ],
  3: [
    ["needs_help_daily_activities", "Does your parent need help with daily activities (bathing, eating, dressing)?"],
    ["needs_daily_help_memory", "Does your parent need help with daily activities because of memory loss?"],
    ["has_dementia_or_alzheimers", "Has a doctor diagnosed your parent with dementia or Alzheimer's?"],
    ["has_disability", "Does your parent have a disability that limits work or daily activities?"],
    ["in_nursing_home", "Does your parent live in a nursing home?"],
    ["has_medicare", "Does your parent have Medicare?"],
  ],
  // Step 5 is about the caregiver (Dependent Care Credit)
  5: [
    ["lives_with_caregiver_over_half_year", "Did your parent live with you for more than half of the year?"],
    ["caregiver_provides_over_half_support", "Do you provide more than 50% of your parent's total support for the year (housing, food, medical care)?"],
    ["caregiver_works", "Do you work or look for work, and is the care needed so that you can work?"],
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

/** "2026-11-30" -> "11/30/2026" (US format) */
export const formatDate = (iso) => {
  const [y, m, d] = iso.split("-");
  return `${m}/${d}/${y}`;
};

/** Labels for the machine status values returned by the API */
export const STATUS_LABELS = { possible: "Possible", "needs review": "Needs review", unlikely: "Unlikely" };

/** Step validation: returns an error message or null. */
export function validateStep(step, form) {
  if (step === 1 && form.age.trim() !== "") {
    const age = Number(form.age);
    if (!Number.isInteger(age) || age < 0 || age > 130) return "Age must be a whole number from 0 to 130, or left blank.";
  }
  if (step === 4) {
    for (const [field, label] of [["income", "Annual income"], ["netWorth", "Net worth"]]) {
      if (form[field].trim() !== "" && parseCents(form[field]) === null) {
        return `${label}: enter a dollar amount such as 15000 or 15000.50, or leave it blank.`;
      }
    }
  }
  return null;
}

/** Form -> request body. "Not sure" and blank fields become null (never false or 0). */
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

/** Result -> plain text for copying. Only texts from the API response. */
export function resultToText(result) {
  const lines = ["Benefits check for a parent (preliminary)", ""];
  for (const p of result.programs) {
    lines.push(`${p.name} — ${STATUS_LABELS[p.status] ?? p.status}`, p.result_description);
    if (p.reasons.length) lines.push("What points against it:", ...p.reasons.map((r) => `- ${r}`));
    if (p.to_check.length) lines.push("What to review:", ...p.to_check.map((r) => `- ${r}`));
    if (p.documents.length) lines.push("Documents:", ...p.documents.map((r) => `- ${r}`));
    lines.push(`Primary source: ${p.source_url}`);
    for (const url of p.amounts_source_urls) lines.push(`Amounts source: ${url}`);
    if (p.amounts_valid_until) lines.push(`Amounts valid until: ${formatDate(p.amounts_valid_until)}`);
    if (p.amounts_note) lines.push(`Amounts: ${p.amounts_note}`);
    lines.push(`Rules last verified: ${formatDate(p.last_verified)}`, "");
  }
  lines.push(result.disclaimer);
  return lines.join("\n");
}
