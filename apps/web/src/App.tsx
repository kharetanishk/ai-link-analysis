import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { analyze, ApiError, type AnalysisResponse } from "./api";
import { Audience, Competitors, RawJson, SearchQueries, SEO, Services } from "./sections";
import { setTheme, type Theme } from "./theme";
import { Icon, LogoMark, ResultsSkeleton } from "./ui";

const TABS = [
  { id: "competitors", label: "Competitors", icon: "swords", View: Competitors },
  { id: "queries", label: "Search queries", icon: "query", View: SearchQueries },
  { id: "seo", label: "SEO", icon: "chart", View: SEO },
  { id: "services", label: "Services", icon: "briefcase", View: Services },
  { id: "audience", label: "Audience", icon: "users", View: Audience },
  { id: "json", label: "JSON", icon: "code", View: RawJson },
] as const;

const FEATURES = [
  { icon: "swords", title: "Competitors", text: "Who you compete with, and where you win." },
  { icon: "query", title: "Search queries", text: "What customers type on Google, LinkedIn & more." },
  { icon: "chart", title: "SEO", text: "Keywords, a better title and a technical check." },
  { icon: "briefcase", title: "Services", text: "Your five most important offerings." },
  { icon: "users", title: "Audience", text: "The segments worth marketing to." },
];

const EXAMPLES = ["stripe.com", "notion.so", "zerodha.com", "canva.com"];
const STEPS = ["Checking the link", "Reading the website", "Understanding the business", "Researching competitors & SEO", "Writing your report"];

const TIPS: Record<string, string> = {
  invalid_url: "Type the address as it appears in your browser, e.g. example.com",
  invalid_request: "Type the address as it appears in your browser, e.g. example.com",
  blocked_url: "Only public websites can be analyzed.",
  site_access_denied: "Some websites block automated tools. Try another page of the site, or a different site.",
  site_unreachable: "Open the link in your browser to check that it works.",
  site_timeout: "The site is slow right now. Try again in a minute.",
  insufficient_content: "Try a specific page such as /about or /services.",
  rate_limited: "You've made many requests in a short time. Wait a minute and try again.",
  llm_unavailable: "The AI is busy. Waiting a minute usually fixes this.",
  llm_invalid_output: "This happens rarely. Trying again usually works.",
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
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const setTab = (t: TabId) => {
    setTabState(t);
    history.replaceState(null, "", `${location.search}#${t}`);
  };
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setThemeState(next);
  };

  const run = async (target: string) => {
    const value = target.trim();
    if (!value) return input.current?.focus();
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

  const reset = () => {
    controller.current?.abort();
    setState({ kind: "idle" });
    setUrl("");
    history.replaceState(null, "", "/");
  };

  const idle = state.kind === "idle";
  const loading = state.kind === "loading";

  return (
    <div className="app">
      <nav className="topbar">
        <a className="wordmark" href="/" onClick={(e) => { e.preventDefault(); reset(); }}>
          <LogoMark size={26} />
          LinkLens
        </a>
        <div className="topbar-actions">
          <a className="nav-link" href="/docs" target="_blank" rel="noopener">API</a>
          <button type="button" className="icon-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
            <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
          </button>
        </div>
      </nav>

      <header className={`hero ${idle ? "" : "compact"}`}>
        {idle && (
          <>
            <p className="eyebrow">AI website intelligence</p>
            <h1>Know any business <em>from its website.</em></h1>
            <p className="lede">Paste a link. Get competitors, search queries, SEO fixes, services and audience — in about twenty seconds.</p>
          </>
        )}
        <form className="search" onSubmit={submit} role="search">
          <label className="search-field">
            <span className="search-label">Website</span>
            <input
              ref={input}
              type="text"
              inputMode="url"
              autoComplete="url"
              spellCheck={false}
              placeholder="stripe.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              maxLength={2048}
              aria-label="Website address"
            />
          </label>
          <button type="submit" className="search-btn" disabled={loading} aria-label="Analyze website">
            {loading ? <span className="spinner" aria-hidden="true" /> : <Icon name="search" size={16} />}
            <span>{loading ? "Analyzing" : "Analyze"}</span>
          </button>
        </form>
        {idle && (
          <div className="examples">
            <span>Try</span>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="example" onClick={() => run(ex)}>{ex}</button>
            ))}
          </div>
        )}
      </header>

      <main className="content">
        {idle && (
          <ul className="features">
            {FEATURES.map((f) => (
              <li key={f.title}>
                <Icon name={f.icon} size={18} />
                <strong>{f.title}</strong>
                <span>{f.text}</span>
              </li>
            ))}
          </ul>
        )}
        {loading && <Loading />}
        {state.kind === "error" && <ErrorCard state={state} onRetry={() => run(state.url)} />}
        {state.kind === "done" && <Results data={state.data} tab={tab} setTab={setTab} />}
      </main>

      <footer className="footer">Insights are AI-generated from a website's public content. Verify before acting.</footer>
    </div>
  );
}

function Loading() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 3500);
    return () => clearInterval(id);
  }, []);
  return (
    <div aria-live="polite" aria-busy="true">
      <div className="progress">
        <span className="progress-label">{STEPS[step]}…</span>
        <span className="progress-count">{step + 1} / {STEPS.length}</span>
        <div className="progress-track"><div className="progress-bar" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} /></div>
      </div>
      <ResultsSkeleton />
    </div>
  );
}

function ErrorCard({ state, onRetry }: { state: Extract<State, { kind: "error" }>; onRetry: () => void }) {
  const { error } = state;
  return (
    <div className="error-card" role="alert">
      <span className="error-icon"><Icon name="alert" size={18} /></span>
      <div>
        <h3>{error.message}</h3>
        {TIPS[error.code] && <p className="muted">{TIPS[error.code]}</p>}
        <div className="row">
          <button type="button" className="btn-dark" onClick={onRetry}>Try again</button>
          {error.requestId && <span className="muted small">Ref {error.requestId.slice(0, 12)}</span>}
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
        <div className="monogram" aria-hidden="true">{data.brand.name.slice(0, 1).toUpperCase()}</div>
        <div className="brand-body">
          <p className="eyebrow">{data.brand.category}</p>
          <h2>{data.brand.name}</h2>
          <p className="brand-summary">{data.brand.summary}</p>
          <a className="link" href={data.website} target="_blank" rel="noopener noreferrer nofollow">{host} <Icon name="external" size={12} /></a>
        </div>
        <dl className="stats">
          <div><dt>Time</dt><dd>{(meta.latency_ms / 1000).toFixed(1)}s</dd></div>
          <div><dt>Pages read</dt><dd>{meta.pages_analyzed.length}</dd></div>
          <div><dt>AI cost</dt><dd>{meta.cached ? "Cached" : `$${meta.estimated_cost_usd.toFixed(3)}`}</dd></div>
        </dl>
      </section>

      {meta.warnings.length > 0 && (
        <div className="notice" role="status">
          <Icon name="alert" size={15} />
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
            <Icon name={t.icon} size={16} />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <div id="panel" role="tabpanel" aria-labelledby={`tab-${active.id}`} className="panel" key={active.id}>
        <active.View data={data} />
      </div>

      <p className="meta-line">
        {meta.model} · {meta.tokens.input.toLocaleString()} in / {(meta.tokens.output + meta.tokens.thinking).toLocaleString()} out tokens · {new Date(meta.analyzed_at).toLocaleString()}
      </p>
    </div>
  );
}
