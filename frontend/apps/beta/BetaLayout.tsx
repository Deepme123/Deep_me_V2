import { NavLink, Outlet } from "react-router-dom";

const betaLinks = [
  { to: "/beta", label: "베타 홈", end: true },
  { to: "/beta/chat", label: "대화" },
  { to: "/beta/result/example-session", label: "결과 예시" },
];

export function BetaLayout() {
  return (
    <main className="route-shell">
      <header className="route-header">
        <div>
          <p className="eyebrow">DeepMe Beta</p>
          <h1>일반 베타 사용자 화면</h1>
        </div>
        <nav className="route-nav" aria-label="베타 탐색">
          {betaLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Outlet />
    </main>
  );
}
