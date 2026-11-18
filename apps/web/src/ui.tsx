import { useState, type ReactNode } from "react";

const paths: Record<string, string> = {
  search: "M11 4a7 7 0 1 0 4.4 12.4l4.1 4.1 1.4-1.4-4.1-4.1A7 7 0 0 0 11 4Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z",
  copy: "M8 3h10a2 2 0 0 1 2 2v12h-2V5H8V3Zm-3 4h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Zm0 2v10h10V9H5Z",
  check: "M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6L20.1 8.4 18.7 7z",
  download: "M11 4h2v8.6l3.3-3.3 1.4 1.4L12 16.4l-5.7-5.7 1.4-1.4 3.3 3.3V4ZM5 18h14v2H5v-2Z",
  external: "M14 4h6v6h-2V7.4l-7.3 7.3-1.4-1.4L16.6 6H14V4ZM5 6h6v2H6v10h10v-5h2v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z",
  swords: "M4 4h5l9 9 1.5-1.5 1.4 1.4-2.1 2.1 2.2 2.2-2.8 2.8-2.2-2.2-2.1 2.1-1.4-1.4L14 17l-9-9V4Zm2 2v1.2l8.5 8.5 1.2-1.2L7.2 6H6Z",
  query: "M4 5h16v2H4V5Zm0 6h10v2H4v-2Zm0 6h7v2H4v-2Zm13.5-4a3.5 3.5 0 0 1 2.9 5.4l1.8 1.8-1.4 1.4-1.8-1.8A3.5 3.5 0 1 1 17.5 13Zm0 2a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z",
  chart: "M4 19h16v2H4v-2Zm1-8h3v6H5v-6Zm5-4h3v10h-3V7Zm5 3h3v7h-3v-7Z",
  briefcase: "M9 4h6a2 2 0 0 1 2 2v1h3a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h3V6a2 2 0 0 1 2-2Zm0 3h6V6H9v1ZM5 9v9h14V9H5Z",
  users: "M9 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm0 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm7.5 1a3 3 0 1 1 0 6 3 3 0 0 1 0-6ZM2 19c0-3 3.1-5 7-5s7 2 7 5v1h-2v-1c0-1.6-2.1-3-5-3s-5 1.4-5 3v1H2v-1Zm15.5-3.9c2.6.3 4.5 1.8 4.5 3.9v1h-2v-1c0-.9-.9-1.6-2.5-1.9v-2Z",
  code: "m8.6 7.4-4.6 4.6 4.6 4.6L7.2 18l-6-6 6-6 1.4 1.4Zm6.8 0L16.8 6l6 6-6 6-1.4-1.4 4.6-4.6-4.6-4.6Z",
  alert: "M12 3 2 21h20L12 3Zm0 4.5 6.6 11.5H5.4L12 7.5ZM11 11h2v4h-2v-4Zm0 5h2v2h-2v-2Z",
  sun: "M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM11 1h2v3h-2V1Zm0 19h2v3h-2v-3ZM3.5 4.9l1.4-1.4 2.1 2.1-1.4 1.4-2.1-2.1Zm13 13 1.4-1.4 2.1 2.1-1.4 1.4-2.1-2.1ZM1 11h3v2H1v-2Zm19 0h3v2h-3v-2ZM4.9 20.5l-1.4-1.4 2.1-2.1 1.4 1.4-2.1 2.1Zm13-13-1.4-1.4 2.1-2.1 1.4 1.4-2.1 2.1Z",
  moon: "M12.3 2a8 8 0 0 0 9.7 9.7A10 10 0 1 1 12.3 2Zm-2.6 2.6a8 8 0 1 0 9.7 9.7 10 10 0 0 1-9.7-9.7Z",
  sparkle: "M12 2l2.1 6.4L20.5 10l-6.4 2.1L12 18.5l-2.1-6.4L3.5 10l6.4-1.6L12 2Zm7 13 1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3Z",
};

export function Icon({ name, size = 18 }: { name: keyof typeof paths | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
}

export function Chips({ items, tone }: { items: string[]; tone?: "accent" | "muted" }) {
  if (!items?.length) return <span className="muted">—</span>;
  return (
    <div className="chips">
      {items.map((item) => (
        <span key={item} className={`chip ${tone ?? ""}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

export function List({ items }: { items: string[] }) {
  if (!items?.length) return <p className="muted">Nothing identified.</p>;
  return (
    <ul className="list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
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
            {subtitle && <p className="muted small">{subtitle}</p>}
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
      <Icon name={copied ? "check" : "copy"} size={16} />
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
          <tr>
            {head.map((h) => (
              <th key={h} scope="col">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} data-label={head[j]}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
