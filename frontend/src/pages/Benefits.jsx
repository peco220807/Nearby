import { Link } from "react-router-dom";
import Eligibility from "../components/Eligibility/Eligibility.jsx";

// Скрининг льгот не привязан к семье и ничего не сохраняет
export default function Benefits() {
  return (
    <main>
      <p style={{ padding: "0 16px" }}>
        <Link to="/">← На главную</Link>
      </p>
      <Eligibility />
    </main>
  );
}
