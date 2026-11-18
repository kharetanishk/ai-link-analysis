import { useState, type ReactNode } from "react";

// thin-stroke icons (24px grid), ek hi visual weight poore UI me
const paths: Record<string, string> = {
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm9 2-4-4",
  copy: "M9 9h10v10H9zM5 15V5h10",
  check: "m5 12 5 5L20 7",
  download: "M12 4v11m0 0-4-4m4 4 4-4M5 20h14",
  external: "M14 5h5v5m0-5-8 8M10 5H5v14h14v-5",
  swords: "M4 20 20 4M14 4h6v6M10 20H4v-6",
  query: "M4 6h16M4 12h9M4 18h6m10 1-2.5-2.5M15.5 17a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  chart: "M4 20h16M7 16v-5m5 5V7m5 9v-8",
  briefcase: "M4 8h16v11H4zM9 8V5h6v3M4 13h16",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm-6 9c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14.8c1.8.6 3 2.4 3 5.2",
  code: "m8 7-5 5 5 5m8-10 5 5-5 5",
  alert: "M12 4 2.5 20h19L12 4Zm0 6v4m0 3v.01",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0-14v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z",
};

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
}

export function LogoMark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" className="logo-mark">
      <circle cx="14" cy="14" r="10" strokeWidth={2.4} />
      <path d="m21.5 21.5 6.5 6.5" strokeWidth={2.8} />
      <path d="m12.6 11.4 1.6-1.6a2.4 2.4 0 0 1 3.4 3.4L16 14.8M15.4 16.6l-1.6 1.6a2.4 2.4 0 0 1-3.4-3.4l1.6-1.6M12.5 15.5l3-3" strokeWidth={1.9} />
    </svg>
  );
}

export function Chips({ items, tone }: { items: string[]; tone?: "accent" | "muted" }) {
  if (!items?.length) return <span className="muted">—</span>;
  return (
    <div className="chips">
      {items.map((item) => (
        <span key={item} className={`chip ${tone ?? ""}`}>{item}</span>
      ))}
    </div>
  );
}

export function List({ items }: { items: string[] }) {
  if (!items?.length) return <p className="muted">Nothing identified.</p>;
  return (
    <ul className="list">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  );
}

export function Card({ title, subtitle, children, actions }: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p className="card-sub">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="field">
      <span className="label">{label}</span>
      <div>{children}</div>
    </div>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <button type="button" className="btn-ghost" onClick={copy} aria-live="polite">
      <Icon name={copied ? "check" : "copy"} size={14} />
      {copied ? "Copied" : label}
    </button>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" | "accent" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{head.map((h) => <th key={h} scope="col">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => <td key={j} data-label={head[j]}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Skeleton({ w = "100%", h = 12, r = 6, className = "" }: { w?: string | number; h?: number; r?: number; className?: string }) {
  return <span className={`skeleton ${className}`} style={{ width: w, height: h, borderRadius: r }} />;
}

function SkeletonCard({ lines = 3, table = false }: { lines?: number; table?: boolean }) {
  return (
    <div className="card">
      <Skeleton w="32%" h={16} />
      <div className="sk-gap" />
      {table
        ? [0, 1, 2, 3].map((i) => (
            <div key={i} className="sk-row">
              <Skeleton w="18%" /><Skeleton w="22%" /><Skeleton w="26%" /><Skeleton w="20%" />
            </div>
          ))
        : Array.from({ length: lines }, (_, i) => <Skeleton key={i} w={`${92 - i * 14}%`} className="sk-line" />)}
    </div>
  );
}

export function ResultsSkeleton() {
  return (
    <div className="results skeleton-results" aria-hidden="true">
      <section className="brand">
        <Skeleton w={64} h={64} r={16} />
        <div className="brand-body">
          <Skeleton w={140} h={10} />
          <Skeleton w={220} h={34} r={8} className="sk-line" />
          <Skeleton w="90%" className="sk-line" />
          <Skeleton w="70%" className="sk-line" />
        </div>
        <div className="stats">
          {[0, 1, 2].map((i) => <Skeleton key={i} w={84} h={52} r={12} />)}
        </div>
      </section>
      <div className="tabs">
        {[90, 110, 50, 70, 80, 50].map((w, i) => <Skeleton key={i} w={w} h={14} className="sk-tab" />)}
      </div>
      <div className="stack">
        <SkeletonCard lines={4} />
        <SkeletonCard table />
        <div className="grid-2">
          <SkeletonCard lines={3} />
          <SkeletonCard lines={3} />
        </div>
      </div>
    </div>
  );
}
