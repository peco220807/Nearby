import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createHousehold } from "../api.js";

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
      setError("Добавьте хотя бы одного участника");
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
    <main>
      <h1>Nearby</h1>
      <p>
        <Link to="/benefits">Проверить льготы для родителя</Link> — без создания семьи, ответы не сохраняются.
      </p>
      <h2>Создать семью</h2>
      <form onSubmit={onSubmit}>
        <p>
          <label>
            Название семьи{" "}
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
          </label>
        </p>
        <p>
          <label>
            Имя родителя{" "}
            <input value={parentName} onChange={(e) => setParentName(e.target.value)} maxLength={120} />
          </label>
        </p>
        <fieldset>
          <legend>Участники</legend>
          {members.map((m, i) => (
            <p key={i}>
              <input value={m} onChange={(e) => setMember(i, e.target.value)} placeholder={`Участник ${i + 1}`} />
              {members.length > 1 && (
                <button type="button" onClick={() => setMembers(members.filter((_, j) => j !== i))}>
                  Убрать
                </button>
              )}
            </p>
          ))}
          {members.length < 10 && (
            <button type="button" onClick={() => setMembers([...members, ""])}>
              Добавить участника
            </button>
          )}
        </fieldset>
        {error && <p role="alert">Ошибка: {error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Создаём…" : "Создать"}
        </button>
      </form>
    </main>
  );
}
