import type { AnalysisResponse, SEOIssue } from "./api";
import { Badge, Card, Chips, CopyButton, Field, Icon, List, Table } from "./ui";

type Props = { data: AnalysisResponse };

export function Competitors({ data }: Props) {
  const c = data.analysis.competitor_analysis;
  const grounded = c.competitors.some((x) => x.source === "web_grounded");
  return (
    <div className="stack">
      <Card title="Your brand at a glance">
        <p className="lead">{c.brand_overview}</p>
        <div className="grid-2">
          <Field label="Business category">{c.business_category}</Field>
          <Field label="Target market">{c.your_target_market}</Field>
          <Field label="Key strength">{c.your_key_strength}</Field>
        </div>
        <div className="sk-gap" />
        <Field label="Products & services"><Chips items={c.products_and_services} /></Field>
      </Card>

      <Card
        title="Competitor comparison"
        subtitle={c.disclaimer}
        actions={<Badge tone={grounded ? "good" : "warn"}>{grounded ? "Web-grounded" : "AI-suggested"}</Badge>}
      >
        {c.competitors.length ? (
          <Table
            head={["Brand", "Main service", "Target market", "Strengths", "Weaknesses / gaps"]}
            rows={[
              [
                <strong className="you">{data.brand.name} <Badge tone="accent">You</Badge></strong>,
                c.products_and_services[0] ?? "—",
                c.your_target_market,
                <List items={c.strengths.slice(0, 3)} />,
                "—",
              ],
              ...c.competitors.map((comp) => [
                <div>
                  <strong>{comp.name}</strong>
                  {comp.website && (
                    <a className="link small" href={comp.website} target="_blank" rel="noopener noreferrer nofollow">
                      {comp.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")} <Icon name="external" size={12} />
                    </a>
                  )}
                </div>,
                comp.main_service,
                comp.target_market,
                <List items={comp.strengths} />,
                <List items={comp.weaknesses} />,
              ]),
            ]}
          />
        ) : (
          <p className="muted">No reliable competitors could be identified for this website.</p>
        )}
      </Card>

      <div className="grid-2">
        <Card title="Your competitive advantages"><List items={c.strengths} /></Card>
        <Card title="Opportunities to improve positioning"><List items={c.opportunities} /></Card>
      </div>
    </div>
  );
}

export function SearchQueries({ data }: Props) {
  const { target_search_queries: queries, search_queries_note: note } = data.analysis;
  return (
    <Card title="Top 5 target search queries" subtitle={note.reason}>
      <Table
        head={["Search query", "Platforms", "Intent", "Why it matters", "Audience"]}
        rows={queries.map((q) => [
          <span className="query">“{q.query}”</span>,
          <div className="platforms">{q.platforms.map((p) => <span key={p} className={`platform ${p.toLowerCase()}`}>{p}</span>)}</div>,
          <Badge>{q.intent}</Badge>,
          q.business_relevance,
          q.target_audience,
        ])}
      />
    </Card>
  );
}

const statusTone: Record<SEOIssue["status"], "good" | "warn" | "bad"> = { pass: "good", warn: "warn", fail: "bad" };

function MetaCompare({ label, current, recommended, ideal }: { label: string; current: string; recommended: string; ideal: [number, number] }) {
  const fits = (s: string) => s.length >= ideal[0] && s.length <= ideal[1];
  return (
    <div className="compare">
      <div className="compare-col">
        <span className="label">Current {label}</span>
        <p className={current ? "" : "muted"}>{current || "Not set"}</p>
        <span className={`count ${fits(current) ? "ok" : ""}`}>{current.length} chars</span>
      </div>
      <div className="compare-col recommended">
        <span className="label">Recommended {label} <CopyButton text={recommended} /></span>
        <p>{recommended}</p>
        <span className={`count ${fits(recommended) ? "ok" : ""}`}>{recommended.length} chars · ideal {ideal[0]}–{ideal[1]}</span>
      </div>
    </div>
  );
}

export function SEO({ data }: Props) {
  const s = data.analysis.seo_improvements;
  const score = Math.round((s.technical_audit.filter((i) => i.status === "pass").length / Math.max(s.technical_audit.length, 1)) * 100);
  return (
    <div className="stack">
      <Card title="Keyword recommendations">
        <div className="grid-2">
          <Field label="Primary keyword"><span className="chip accent big">{s.primary_keyword}</span></Field>
          <Field label="Secondary keywords"><Chips items={s.secondary_keywords} /></Field>
          <Field label="Long-tail keywords"><Chips items={s.long_tail_keywords} tone="muted" /></Field>
          <Field label="Business keywords"><Chips items={s.business_keywords} tone="muted" /></Field>
        </div>
      </Card>

      <Card title="SEO title & meta description" subtitle={`Title structure: ${s.title_structure}`}>
        <MetaCompare label="title" current={s.current_title} recommended={s.recommended_title} ideal={[30, 60]} />
        <MetaCompare label="meta description" current={s.current_meta_description} recommended={s.meta_description} ideal={[120, 160]} />
      </Card>

      <Card title="Technical SEO check" subtitle="Measured directly from the page HTML" actions={<Badge tone={score >= 80 ? "good" : score >= 50 ? "warn" : "bad"}>{score}% passed</Badge>}>
        <ul className="audit">
          {s.technical_audit.map((i) => (
            <li key={i.check}>
              <span className={`dot ${statusTone[i.status]}`} aria-label={i.status} />
              <div>
                <strong>{i.check}</strong> <span className="muted">· {i.finding}</span>
                {i.recommendation && <p className="small">{i.recommendation}</p>}
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Content to add for more search visibility">
        <div className="tiles">
          {s.supporting_content.map((item) => (
            <div key={item.title} className="tile">
              <Badge>{item.type === "faq" ? "FAQ" : item.type.replace(/_/g, " ")}</Badge>
              <strong>{item.title}</strong>
              <p className="muted small">{item.purpose}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export function Services({ data }: Props) {
  return (
    <div className="tiles services">
      {data.analysis.top_services.map((s, i) => (
        <article key={s.name} className="card service">
          <div className="service-head">
            <span className="rank">No. {String(i + 1).padStart(2, "0")}</span>
            <Badge tone={s.source === "website" ? "good" : "warn"}>{s.source === "website" ? "From website" : "Inferred"}</Badge>
          </div>
          <h3>{s.name}</h3>
          <p className="muted">{s.description}</p>
          <div className="service-meta">
            <Field label="Industry">{s.target_industry}</Field>
            <Field label="Customer">{s.target_customer}</Field>
            <Field label="Main benefit">{s.main_benefit}</Field>
          </div>
        </article>
      ))}
    </div>
  );
}

export function Audience({ data }: Props) {
  const a = data.analysis.target_audience;
  return (
    <div className="stack">
      <div className="grid-2">
        <Card title="Primary audience"><List items={a.primary_audience} /></Card>
        <Card title="Secondary audience"><List items={a.secondary_audience} /></Card>
      </div>
      <Card title="Recommended marketing segments">
        <Table
          head={["Segment", "Business type", "What they need"]}
          rows={a.recommended_segments.map((s) => [<strong>{s.segment}</strong>, s.business_type, s.requirement])}
        />
      </Card>
      <Card title="Audience profile">
        <div className="grid-2">
          <Field label="Industries"><Chips items={a.industries} /></Field>
          <Field label="Business types"><Chips items={a.business_types} /></Field>
          <Field label="Geographic focus">{a.geographic_focus ?? <span className="muted">Not specified on the website</span>}</Field>
          <Field label="Interests"><Chips items={a.interests} tone="muted" /></Field>
        </div>
      </Card>
      <div className="grid-3">
        <Card title="Customer profiles"><List items={a.customer_profiles} /></Card>
        <Card title="Needs"><List items={a.customer_needs} /></Card>
        <Card title="Challenges"><List items={a.challenges} /></Card>
      </div>
    </div>
  );
}

export function RawJson({ data }: Props) {
  const json = JSON.stringify(data, null, 2);
  const download = () => {
    const blob = new Blob([json], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `link-analysis-${new URL(data.website).hostname}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <Card
      title="Raw API response"
      subtitle="The exact JSON returned by POST /link-analysis"
      actions={
        <div className="row">
          <CopyButton text={json} label="Copy JSON" />
          <button type="button" className="btn-ghost" onClick={download}><Icon name="download" size={14} />Download</button>
        </div>
      }
    >
      <pre className="json">{json}</pre>
    </Card>
  );
}
