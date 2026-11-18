import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { analyze, ApiError, type AnalysisResponse } from "./api";
import { Audience, Competitors, RawJson, SearchQueries, SEO, Services } from "./sections";
import { setTheme, type Theme } from "./theme";
import { Badge, Icon } from "./ui";

const TABS = [
  { id: "competitors", label: "Competitors", icon: "swords", View: Competitors },
  { id: "queries", label: "Search queries", icon: "query", View: SearchQueries },
  { id: "seo", label: "SEO", icon: "chart", View: SEO },
  { id: "services", label: "Top services", icon: "briefcase", View: Services },
  { id: "audience", label: "Audience", icon: "users", View: Audience },
  { id: "json", label: "JSON", icon: "code", View: RawJson },
] as const;

const EXAMPLES = ["stripe.com", "notion.so", "zerodha.com", "canva.com"];
const STEPS = ["Checking the link", "Reading the website", "Understanding the business", "Researching competitors & SEO", "Putting your report together"];

const TIPS: Record<string, string> = {
  invalid_url: "Type the address as it appears in your browser, e.g. example.com",
  invalid_request: "Type the address as it appears in your browser, e.g. example.com",
  blocked_url: "Only public websites can be analyzed.",
  site_access_denied: "Some websites block automated tools. Try the company's other pages or a different site.",
  site_unreachable: "Open the link in your browser to check that it works.",
  site_timeout: "The site is slow right now. Try again in a minute.",
  insufficient_content: "Try a specific page such as /about or /services.",
  rate_limited: "You've made many requests in a short time. Wait a minute and try again.",
  llm_unavailable: "The AI is busy. Waiting a minute usually fixes this.",
};

type TabId = (typeof TABS)[number]["id"];

function tabFromHash(): TabId {
  const id = location.hash.slice(1);
  return TABS.find((t) => t.id === id)?.id ?? "competitors";
}

type State =
  | { kind: "idle" }
  | { kind: "loading"; url: string }
  | { kind: "error"; url: string; error: ApiError }
  | { kind: "done"; data: AnalysisResponse };

export default function App() {
  const [url, setUrl] = useState(() => new URLSearchParams(location.search).get("url") ?? "");
  const [state, setState] = useState<State>({ kind: "idle" });
  const [tab, setTabState] = useState<TabId>(() => tabFromHash());
  const [theme, setThemeState] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme) ?? "light");
  const setTab = (t: TabId) => {
    setTabState(t);
    history.replaceState(null, "", `${location.search}#${t}`);
  };
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setThemeState(next);
  };
  const controller = useRef<AbortController | null>(null);

  const run = async (target: string) => {
    const value = target.trim();
    if (!value) return;
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setUrl(value);
    setState({ kind: "loading", url: value });
    history.replaceState(null, "", `?url=${encodeURIComponent(value)}${location.hash}`);
    try {
      const data = await analyze(value, ctrl.signal);
      setState({ kind: "done", data });
    } catch (err) {
      if (ctrl.signal.aborted) return;
      setState({ kind: "error", url: value, error: err instanceof ApiError ? err : new ApiError("unknown", "Something went wrong.") });
    }
  };

  useEffect(() => {
    if (url) run(url);
    return () => controller.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(url);
  };

  const compact = state.kind !== "idle";

  return (
    <div className="app">
      <nav className="topbar">
        <a className="logo" href="/" onClick={(e) => { e.preventDefault(); controller.current?.abort(); setState({ kind: "idle" }); setUrl(""); history.replaceState(null, "", "/"); }}>
          <span className="logo-mark"><Icon name="sparkle" size={18} /></span>
          linklens
        </a>
        <div className="topbar-actions">
          <button type="button" className="btn-ghost icon-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
            <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
          </button>
          <a className="btn-ghost" href="/docs" target="_blank" rel="noopener">API docs <Icon name="external" size={14} /></a>
        </div>
      </nav>

      <header className={`hero ${compact ? "compact" : ""}`}>
        {!compact && (
          <>
            <h1>Understand any business<br />from just its website.</h1>
            <p className="muted">Competitors, search queries, SEO fixes, top services and target audience — in one click.</p>
          </>
        )}
        <form className="search" onSubmit={submit} role="search">
          <label htmlFor="url" className="search-label">Website</label>
          <input
            id="url"
            type="text"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            placeholder="Paste a website, e.g. stripe.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            maxLength={2048}
          />
          <button type="submit" className="search-btn" disabled={!url.trim() || state.kind === "loading"} aria-label="Analyze website">
            <Icon name="search" size={18} />
            <span>{state.kind === "loading" ? "Analyzing" : "Analyze"}</span>
          </button>
        </form>
        {!compact && (
          <div className="examples">
            <span className="muted small">Try:</span>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="chip clickable" onClick={() => run(ex)}>{ex}</button>
            ))}
          </div>
        )}
      </header>

      <main className="content">
        {state.kind === "loading" && <Loading />}
        {state.kind === "error" && <ErrorCard state={state} onRetry={() => run(state.url)} />}
        {state.kind === "done" && <Results data={state.data} tab={tab} setTab={setTab} />}
      </main>

      <footer className="footer muted small">Insights are AI-generated from the website's public content. Always verify before acting.</footer>
    </div>
  );
}

function Loading() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2800);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="loading" aria-live="polite" aria-busy="true">
      <ol className="steps">
        {STEPS.map((label, i) => (
          <li key={label} className={i < step ? "done" : i === step ? "active" : ""}>
            <span className="step-dot">{i < step ? <Icon name="check" size={12} /> : null}</span>
            {label}
          </li>
        ))}
      </ol>
      <div className="skeleton-grid">
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" />)}
      </div>
    </div>
  );
}

function ErrorCard({ state, onRetry }: { state: Extract<State, { kind: "error" }>; onRetry: () => void }) {
  const { error } = state;
  return (
    <div className="card error-card" role="alert">
      <span className="error-icon"><Icon name="alert" size={22} /></span>
      <div>
        <h3>{error.message}</h3>
        {TIPS[error.code] && <p className="muted">{TIPS[error.code]}</p>}
        <div className="row">
          <button type="button" className="btn-primary" onClick={onRetry}>Try again</button>
          {error.requestId && <span className="muted small">Reference: {error.requestId}</span>}
        </div>
      </div>
    </div>
  );
}

function Results({ data, tab, setTab }: { data: AnalysisResponse; tab: TabId; setTab: (t: TabId) => void }) {
  const active = TABS.find((t) => t.id === tab) ?? TABS[0];
  const host = new URL(data.website).hostname.replace(/^www\./, "");
  const { meta } = data;

  const onKey = (e: KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.id === tab);
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
    if (next === null) return;
    const t = TABS[(next + TABS.length) % TABS.length];
    setTab(t.id);
    document.getElementById(`tab-${t.id}`)?.focus();
  };

  return (
    <div className="results">
      <section className="brand">
        <div className="brand-avatar" aria-hidden="true">{data.brand.name.slice(0, 1).toUpperCase()}</div>
        <div className="brand-body">
          <div className="row wrap">
            <h2>{data.brand.name}</h2>
            <Badge tone="accent">{data.brand.category}</Badge>
          </div>
          <p>{data.brand.summary}</p>
          <a className="link small" href={data.website} target="_blank" rel="noopener noreferrer nofollow">{host} <Icon name="external" size={12} /></a>
        </div>
        <dl className="stats">
          <div><dt>Time</dt><dd>{(meta.latency_ms / 1000).toFixed(1)}s</dd></div>
          <div><dt>Pages read</dt><dd>{meta.pages_analyzed.length}</dd></div>
          <div><dt>AI cost</dt><dd>{meta.cached ? "cached" : `$${meta.estimated_cost_usd.toFixed(4)}`}</dd></div>
        </dl>
      </section>

      {meta.warnings.length > 0 && (
        <div className="notice" role="status">
          <Icon name="alert" size={16} />
          <div>{meta.warnings.map((w) => <p key={w}>{w}</p>)}</div>
        </div>
      )}

      <div className="tabs" role="tablist" aria-label="Analysis sections" onKeyDown={onKey}>
        {TABS.map((t) => (
          <button
            key={t.id}
            id={`tab-${t.id}`}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            aria-controls="panel"
            tabIndex={tab === t.id ? 0 : -1}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <Icon name={t.icon} size={20} />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <div id="panel" role="tabpanel" aria-labelledby={`tab-${active.id}`} className="panel" key={active.id}>
        <active.View data={data} />
      </div>

      <p className="muted small meta-line">
        Model {meta.model} · {meta.tokens.input.toLocaleString()} input / {(meta.tokens.output + meta.tokens.thinking).toLocaleString()} output tokens · analyzed {new Date(meta.analyzed_at).toLocaleString()}
      </p>
    </div>
  );
}
