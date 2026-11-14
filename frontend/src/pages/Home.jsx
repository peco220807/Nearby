import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createHousehold } from "../api.js";
import Layout from "../components/Layout.jsx";
import { ArrowRight, Hourglass, ShieldCheck, Users } from "../components/icons.jsx";

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Check benefits",
    text: "Answer a few questions and see which programs may apply to your parent, with links to the official sources.",
    to: "/benefits",
    cta: "Check benefits",
  },
  {
    icon: Hourglass,
    title: "See how long savings last",
    text: "Compare in-home care, assisted living and a nursing home against your parent's savings and income.",
    to: "/scenarios",
    cta: "See how long savings last",
  },
  {
    icon: Users,
    title: "Share costs with family",
    text: "A private ledger for siblings: who paid what, who helped when, and who owes whom.",
    to: "#ledger",
    cta: "Share costs with family",
  },
];

export default function Home() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [parentName, setParentName] = useState("");
  const [members, setMembers] = useState(["", ""]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function setMember(i, value) {
    setMembers(members.map((m, j) => (j === i ? value : m)));
  }

  async function onSubmit(e) {
    e.preventDefault();
    const memberNames = members.map((m) => m.trim()).filter(Boolean);
    if (memberNames.length === 0) {
      setError("Add at least one family member.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const household = await createHousehold({
        name: name.trim(),
        parent_name: parentName.trim() || null,
        member_names: memberNames,
      });
      navigate(`/f/${household.share_token}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout home wide>
      <section className="hero">
        <h1>Plan for your parent's care, without the guesswork</h1>
        <p className="lead">
          Caring for a parent raises hard questions about money and time. Nearby helps you see which benefits might
          apply, how long savings could last, and how to share the load with your siblings. No account, nothing sold.
        </p>
      </section>

      <div className="features">
        {FEATURES.map(({ icon: Icon, title, text, to, cta }) => (
          <article key={title} className="card feature">
            <span className="icon-badge">
              <Icon />
            </span>
            <h3>{title}</h3>
            <p className="muted">{text}</p>
            {to.startsWith("#") ? (
              <a href={to} className="btn btn-secondary">
                {cta} <ArrowRight />
              </a>
            ) : (
              <Link to={to} className="btn btn-secondary">
                {cta} <ArrowRight />
              </Link>
            )}
          </article>
        ))}
      </div>

      <section className="card" id="ledger">
        <h2>Start a family ledger</h2>
        <p className="muted">Caring for a parent is shared work. Track who's helping, and what it costs. You get a private link to share with your siblings.</p>
        <form onSubmit={onSubmit}>
          <label className="field">
            Family name
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} placeholder="e.g., The Millers" />
          </label>
          <label className="field">
            Parent's name <span className="field-help">(optional)</span>
            <input value={parentName} onChange={(e) => setParentName(e.target.value)} maxLength={120} placeholder="e.g., Mom" />
          </label>
          <fieldset className="fieldset">
            <legend>Family members</legend>
            {members.map((m, i) => (
              <div key={i} className="row-inline">
                <input
                  className="input"
                  value={m}
                  onChange={(e) => setMember(i, e.target.value)}
                  placeholder={`Member ${i + 1}`}
                  aria-label={`Member ${i + 1}`}
                />
                {members.length > 1 && (
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => setMembers(members.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                )}
              </div>
            ))}
            {members.length < 10 && (
              <p>
                <button type="button" className="btn btn-secondary btn-small" onClick={() => setMembers([...members, ""])}>
                  Add a member
                </button>
              </p>
            )}
          </fieldset>
          {error && (
            <p role="alert" className="alert">
              {error}
            </p>
          )}
          <div className="action-bar">
            <button type="submit" className="btn btn-accent" disabled={busy}>
              {busy ? "Creating…" : "Create the ledger"}
            </button>
          </div>
        </form>
      </section>
    </Layout>
  );
}
