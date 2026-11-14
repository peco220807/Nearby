import { Link, NavLink } from "react-router-dom";
import { Home } from "./icons.jsx";

const NAV = [
  ["/", "Home"],
  ["/benefits", "Benefits check"],
  ["/scenarios", "Care cost calculator"],
];

/** Header with navigation on every page; a "Back to home" link on all pages except home. */
export default function Layout({ children, wide = false, home = false }) {
  return (
    <>
      <header className="site-header">
        <div className="site-header-inner">
          <Link to="/" className="brand">
            <span className="brand-mark">
              <Home width="18" height="18" />
            </span>
            Nearby
          </Link>
          <nav className="site-nav" aria-label="Main">
            {NAV.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"}>
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className={wide ? "page page-wide" : "page"}>
        {!home && (
          <p>
            <Link to="/" className="back-link">
              ← Back to home
            </Link>
          </p>
        )}
        {children}
      </main>
    </>
  );
}
