import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/skills" className="brand">
          <span className="brandMark">S</span>
          <span>
            <strong>SkillHub</strong>
            <small>verified skills</small>
          </span>
        </Link>
        <nav className="nav">
          <Link href="/skills">Hub</Link>
          <Link href="/skills/skill-code-reviewer">Skill</Link>
          <Link href="/eval-set-versions/evalsetver-code-v3">Eval Set</Link>
          <Link href="/eval-runs/evalrun-code-v2-primary">Eval Run</Link>
        </nav>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="pageHeader">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="pageDescription">{description}</p>
      </div>
      {actions ? <div className="headerActions">{actions}</div> : null}
    </header>
  );
}

export function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="section">
      <div className="sectionHeader">
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "bad" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}
