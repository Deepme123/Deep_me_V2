import { NavLink, Outlet } from "react-router-dom";

const adminLinks = [
  { to: "/admin", label: "관리 홈", end: true },
  { to: "/admin/sessions", label: "세션 목록" },
  { to: "/admin/sessions/example-session", label: "상세 예시" },
];

export function AdminLayout() {
  return (
    <main className="route-shell">
      <header className="route-header">
        <div>
          <p className="eyebrow">DeepMe Admin</p>
          <h1>운영자 및 마스터 모니터링 화면</h1>
        </div>
        <nav className="route-nav" aria-label="관리자 탐색">
          {adminLinks.map((link) => (
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
