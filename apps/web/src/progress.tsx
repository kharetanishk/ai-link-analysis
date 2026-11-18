import { useEffect, useRef, useState } from "react";
import type { ProgressEvent } from "./api";
import { Icon } from "./ui";

const VERBS = [
  "Reading between the lines",
  "Cross-referencing competitors",
  "Mapping customer intent",
  "Distilling keywords",
  "Weighing market positioning",
  "Sketching audience profiles",
  "Comparing strengths and gaps",
  "Polishing recommendations",
];

const MILESTONES = [
  { label: "Read the website", stage: "extracted" },
  { label: "Competitors & search queries", stage: "market_ready" },
  { label: "SEO, services & audience", stage: "site_ready" },
  { label: "Refine & assemble the report", stage: "done" },
];

// har stage ke baad bar kahan tak "creep" kar sakta hai, taaki kabhi atka hua na lage
const CEILINGS: [number, number][] = [
  [90, 99],
  [65, 89],
  [40, 64],
  [34, 39],
  [22, 33],
  [0, 21],
];

const ceilingFor = (target: number) => CEILINGS.find(([from]) => target >= from)?.[1] ?? 99;

export function AnalysisProgress({ events, url }: { events: ProgressEvent[]; url: string }) {
  const [value, setValue] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const startedAt = useRef(Date.now());
  const lastEventAt = useRef(Date.now());

  const target = events.reduce((max, e) => (e.percent != null ? Math.max(max, e.percent) : max), 0);
  const last = events[events.length - 1];
  const reached = new Set(events.map((e) => e.stage));

  useEffect(() => {
    lastEventAt.current = Date.now();
  }, [events.length]);

  useEffect(() => {
    const id = setInterval(() => {
      setNow(Date.now());
      setValue((v) => {
        if (v < target) return v + Math.max((target - v) * 0.22, 0.4);
        return Math.min(v + (ceilingFor(target) - v) * 0.015, ceilingFor(target));
      });
    }, 100);
    return () => clearInterval(id);
  }, [target]);

  const quietFor = now - lastEventAt.current;
  const thinking = last && ["analyzing", "market_ready", "site_ready", "fallback"].includes(last.stage) && quietFor > 2500;
  const verb = VERBS[Math.floor((now - startedAt.current) / 2600) % VERBS.length];
  const status = thinking ? `${verb}…` : last?.message ?? "Starting…";
  const elapsed = Math.max(0, Math.floor((now - startedAt.current) / 1000));
  const activeIndex = MILESTONES.findIndex((m) => !reached.has(m.stage));
  const log = events.filter((e) => e.stage !== "done").slice(-4);

  return (
    <section className="cook" aria-live="polite" aria-busy="true">
      <div className="cook-head">
        <div className="cook-percent" aria-label={`${Math.floor(value)} percent complete`}>
          {Math.floor(value)}
          <small>%</small>
        </div>
        <div className="cook-text">
          <p className="cook-status" key={status}>
            <span className="cook-spark" aria-hidden="true" />
            {status}
          </p>
          <p className="cook-sub">{url} · {elapsed}s</p>
        </div>
      </div>

      <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.floor(value)}>
        <div className="progress-bar" style={{ transform: `scaleX(${value / 100})` }} />
      </div>

      <div className="cook-body">
        <ol className="milestones">
          {MILESTONES.map((m, i) => {
            const state = reached.has(m.stage) ? "done" : i === activeIndex ? "active" : "pending";
            return (
              <li key={m.stage} className={state}>
                <span className="milestone-dot">{state === "done" && <Icon name="check" size={11} />}</span>
                {m.label}
              </li>
            );
          })}
        </ol>
        <ul className="cook-log">
          {log.map((e, i) => (
            <li key={`${e.stage}-${i}`} className={i === log.length - 1 ? "latest" : ""}>
              <Icon name={i === log.length - 1 ? "dot" : "check"} size={12} />
              {e.message}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
