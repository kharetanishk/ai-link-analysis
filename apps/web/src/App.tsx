import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { analyzeStream, ApiError, type AnalysisResponse, type ProgressEvent } from "./api";
import { clearHistory, findFresh, loadHistory, removeFromHistory, saveToHistory, timeAgo, type HistoryEntry } from "./history";
import { AnalysisProgress } from "./progress";
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
  ai_quota_exhausted: "LinkLens is open source — clone it and add your own free Gemini key to keep analyzing right away.",
};

type TabId = (typeof TABS)[number]["id"];

function tabFromHash(): TabId {
  const id = location.hash.slice(1);
  return TABS.find((t) => t.id === id)?.id ?? "competitors";
}

type State =
  | { kind: "idle" }
  | { kind: "loading"; url: string; events: ProgressEvent[] }
  | { kind: "error"; url: string; error: ApiError }
  | { kind: "done"; data: AnalysisResponse; savedAt?: number; input: string };

export default function App() {
  const [url, setUrl] = useState(() => new URLSearchParams(location.search).get("url") ?? "");
  const [state, setState] = useState<State>({ kind: "idle" });
  const [tab, setTabState] = useState<TabId>(() => tabFromHash());
  const [theme, setThemeState] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme) ?? "light");
  const controller = useRef<AbortController | null>(null);
  const [recent, setRecent] = useState<HistoryEntry[]>(() => loadHistory());
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

  const open = (entry: HistoryEntry) => {
    controller.current?.abort();
    setUrl(entry.input);
    history.replaceState(null, "", `?url=${encodeURIComponent(entry.input)}${location.hash}`);
    setState({ kind: "done", data: entry.data, savedAt: entry.savedAt, input: entry.input });
  };

  const run = async (target: string, fresh = false) => {
    const value = target.trim();
    if (!value) return input.current?.focus();
    // 24h ke andar ka report is device par hai to turant dikhao, network call nahi
    const saved = fresh ? undefined : findFresh(value);
    if (saved) return open(saved);
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setUrl(value);
    setState({ kind: "loading", url: value, events: [] });
    history.replaceState(null, "", `?url=${encodeURIComponent(value)}${location.hash}`);
    try {
      const data = await analyzeStream(value, ctrl.signal, (event) =>
        setState((s) => (s.kind === "loading" && !ctrl.signal.aborted ? { ...s, events: [...s.events, event] } : s)),
      );
      setRecent(saveToHistory(value, data));
      setState({ kind: "done", data, input: value });
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
          <div className="theme-switch" role="radiogroup" aria-label="Color theme">
            {(["light", "dark"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={theme === t}
                className={theme === t ? "active" : ""}
                onClick={() => theme !== t && toggleTheme()}
              >
                <Icon name={t === "light" ? "sun" : "moon"} size={14} />
                <span>{t === "light" ? "Light" : "Dark"}</span>
              </button>
            ))}
          </div>
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
        {idle && recent.length > 0 && (
          <section className="recent" aria-label="Recent analyses">
            <div className="recent-head">
              <h2>Recent on this device</h2>
              <button type="button" className="text-btn" onClick={() => setRecent(clearHistory())}>Clear</button>
            </div>
            <ul className="recent-list">
              {recent.map((e) => (
                <li key={e.savedAt}>
                  <button type="button" className="recent-card" onClick={() => open(e)}>
                    <span className="recent-mono" aria-hidden="true">{e.data.brand.name.slice(0, 1).toUpperCase()}</span>
                    <span className="recent-text">
                      <strong>{e.data.brand.name}</strong>
                      <span>{new URL(e.data.website).hostname.replace(/^www\./, "")} · {timeAgo(e.savedAt)}</span>
                    </span>
                  </button>
                  <button type="button" className="recent-remove" aria-label={`Remove ${e.data.brand.name}`} onClick={() => setRecent(removeFromHistory(e.savedAt))}>
                    <Icon name="close" size={13} />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
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
        {state.kind === "loading" && (
          <div>
            <AnalysisProgress key={state.url} events={state.events} url={state.url} />
            <ResultsSkeleton />
          </div>
        )}
        {state.kind === "error" && <ErrorCard state={state} onRetry={() => run(state.url)} />}
        {state.kind === "done" && (
          <Results data={state.data} tab={tab} setTab={setTab} savedAt={state.savedAt} onRefresh={() => run(state.input, true)} />
        )}
      </main>

      <footer className="footer">Insights are AI-generated from a website's public content. Verify before acting.</footer>
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
          {error.code === "ai_quota_exhausted" ? (
            <>
              <a className="btn-dark" href={String(error.details.self_host_guide ?? "https://github.com/kharetanishk/ai-link-analysis")} target="_blank" rel="noopener">
                <Icon name="github" size={15} /> Run it yourself
              </a>
              <a className="btn-ghost" href={String(error.details.get_free_key ?? "https://aistudio.google.com/apikey")} target="_blank" rel="noopener noreferrer">
                <Icon name="key" size={14} /> Get a free Gemini key
              </a>
            </>
          ) : (
            <button type="button" className="btn-dark" onClick={onRetry}>Try again</button>
          )}
          {error.requestId && <span className="muted small">Ref {error.requestId.slice(0, 12)}</span>}
        </div>
      </div>
    </div>
  );
}

function Results({ data, tab, setTab, savedAt, onRefresh }: {
  data: AnalysisResponse;
  tab: TabId;
  setTab: (t: TabId) => void;
  savedAt?: number;
  onRefresh: () => void;
}) {
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
          <div><dt>AI cost</dt><dd>{savedAt ? "Saved" : meta.cached ? "Cached" : `$${meta.estimated_cost_usd.toFixed(3)}`}</dd></div>
        </dl>
      </section>

      {savedAt && (
        <div className="saved-note" role="status">
          <span>Opened from this device · analyzed {timeAgo(savedAt)}</span>
          <button type="button" className="text-btn" onClick={onRefresh}>Re-analyze now</button>
        </div>
      )}

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
