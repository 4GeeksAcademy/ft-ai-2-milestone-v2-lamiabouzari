"use client";

import { ChangeEvent, DragEvent, FormEvent, useEffect, useState } from "react";
import { getToken } from "@/lib/auth";

type Incident = { id: string; title: string; category: string; status: string; origin: string; branch: string };
type Summary = Record<string, Record<string, number>>;
type Tab = "manager" | "analysis";

interface IncidentReport {
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_by_reason: Record<string, number>;
  category_breakdown: Record<string, number>;
  category_percentages: Record<string, number>;
  status_breakdown: Record<string, number>;
  status_percentages: Record<string, number>;
  country_breakdown: Record<string, number>;
  country_percentages: Record<string, number>;
  closed_scored_incident_count: number;
  average_satisfaction: number | null;
  score_distribution: Record<string, number>;
  filename?: string;
  analyzed_at?: string;
}

const API = `${(process.env.NEXT_PUBLIC_API_URL || "/api/backend").replace(/\/$/, "")}/api/incidents`;
const branches = [
  { value: "los_angeles", label: "Los Angeles" },
  { value: "zaragoza", label: "Zaragoza" },
  { value: "central", label: "Central" },
];
const categories = ["lost_parcel", "delayed_delivery", "wrong_address", "return_request", "damage"];
const statuses = ["open", "in_progress", "resolved", "discarded"];
const origins = ["customer", "branch", "internal"];
const label = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());

function authHeaders(json = false): Headers {
  const headers = new Headers();
  if (json) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

function errorMessage(payload: { detail?: unknown }, fallback: string): string {
  const detail = payload.detail;
  if (typeof detail === "string" && detail) return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message) return message;
  }
  return fallback;
}

function Breakdown({
  title,
  counts,
  percentages,
}: {
  title: string;
  counts: Record<string, number>;
  percentages?: Record<string, number>;
}) {
  return (
    <section className="dashboard-card p-5">
      <h2 className="font-display text-xl text-foreground">{title}</h2>
      <div className="mt-4 space-y-3">
        {Object.entries(counts).map(([name, count]) => (
          <div key={name}>
            <div className="flex justify-between gap-3 text-sm">
              <span>{name}</span>
              <strong>
                {count}
                {percentages ? ` · ${percentages[name]}%` : ""}
              </strong>
            </div>
            <div className="mt-1 h-2 rounded-full bg-panel-soft">
              <div className="h-2 rounded-full bg-accent" style={{ width: `${percentages?.[name] ?? 0}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function IncidentManager() {
  const [items, setItems] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<Summary>({});
  const [filters, setFilters] = useState({ status: "", origin: "", branch: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    description: "",
    category: categories[0],
    status: "open",
    origin: "customer",
    branch: "",
  });

  async function request(path: string, options?: RequestInit) {
    const headers = authHeaders(true);
    const response = await fetch(`${API}${path}`, { ...options, headers });
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    if (!response.ok) throw Error(errorMessage(body, "Request failed"));
    return body;
  }

  async function load() {
    setLoading(true);
    try {
      const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
      const [listed, totals] = await Promise.all([request(`?${query}`), request("/summary")]);
      setItems(listed as unknown as Incident[]);
      setSummary(totals as unknown as Summary);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load incidents");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    const query = new URLSearchParams(
      [
        ["status", filters.status],
        ["origin", filters.origin],
        ["branch", filters.branch],
      ].filter(([, value]) => value)
    );
    Promise.all([request(`?${query}`), request("/summary")])
      .then(([listed, totals]) => {
        if (cancelled) return;
        setItems(listed as unknown as Incident[]);
        setSummary(totals as unknown as Summary);
        setError("");
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : "Unable to load incidents");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters.status, filters.origin, filters.branch]);

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await request("", { method: "POST", body: JSON.stringify(form) });
      setForm({ ...form, title: "", description: "", branch: "" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create incident");
    }
  }

  async function change(incident: Incident, status: string) {
    const previous = incident.status;
    setItems((current) => current.map((item) => (item.id === incident.id ? { ...item, status } : item)));
    try {
      await request(`/${incident.id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
    } catch (caught) {
      setItems((current) => current.map((item) => (item.id === incident.id ? { ...item, status: previous } : item)));
      setError(caught instanceof Error ? caught.message : "Status update failed");
    }
  }

  return (
    <div className="space-y-6">
      {error ? (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <section className="dashboard-card p-5">
        <h2 className="font-display text-2xl">Register incident</h2>
        <form onSubmit={create} className="mt-4 grid gap-4 md:grid-cols-2">
          <label>
            Title
            <input
              required
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line p-2"
            />
          </label>
          <label>
            Category
            <select
              value={form.category}
              onChange={(event) => setForm({ ...form, category: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line p-2"
            >
              {categories.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="md:col-span-2">
            Description
            <textarea
              required
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line p-2"
            />
          </label>
          <label>
            Origin
            <select
              value={form.origin}
              onChange={(event) => setForm({ ...form, origin: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line p-2"
            >
              {origins.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className={form.origin === "branch" ? "rounded-lg bg-accent-soft p-2 font-semibold" : ""}>
            Branch
            <select
              required
              value={form.branch}
              onChange={(event) => setForm({ ...form, branch: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line p-2"
            >
              <option value="">Select a branch</option>
              {branches.map((branch) => (
                <option value={branch.value} key={branch.value}>
                  {branch.label}
                </option>
              ))}
            </select>
          </label>
          <button className="w-fit rounded-full bg-accent px-5 py-2 font-semibold text-white">Create incident</button>
        </form>
      </section>
      <section className="grid gap-4 md:grid-cols-4">
        {Object.entries(summary).map(([group, values]) => (
          <article className="dashboard-card p-4" key={group}>
            <h2 className="font-semibold capitalize">{group}</h2>
            {Object.entries(values).map(([key, count]) => (
              <p className="mt-2 flex justify-between text-sm" key={key}>
                <span>{label(key)}</span>
                <strong>{count}</strong>
              </p>
            ))}
          </article>
        ))}
      </section>
      <section className="dashboard-card p-5">
        <div className="flex flex-wrap gap-3">
          <h2 className="mr-auto font-display text-2xl">Incidents</h2>
          {(["status", "origin", "branch"] as const).map((key) => (
            <select
              key={key}
              value={filters[key]}
              onChange={(event) => {
                setLoading(true);
                setFilters({ ...filters, [key]: event.target.value });
              }}
              className="rounded-lg border border-line p-2"
            >
              <option value="">All {key}s</option>
              {(key === "status" ? statuses : key === "origin" ? origins : branches.map((branch) => branch.value)).map(
                (value) => (
                  <option key={value} value={value}>
                    {label(value)}
                  </option>
                ),
              )}
            </select>
          ))}
        </div>
        {loading ? (
          <p className="py-8">Loading incidents…</p>
        ) : items.length === 0 ? (
          <p className="py-8">No incidents match the selected filters.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="p-2">Title</th>
                  <th className="p-2">Category</th>
                  <th className="p-2">Branch</th>
                  <th className="p-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((incident) => (
                  <tr className="border-b border-line" key={incident.id}>
                    <td className="p-2">{incident.title}</td>
                    <td className="p-2">{label(incident.category)}</td>
                    <td className="p-2">{label(incident.branch)}</td>
                    <td className="p-2">
                      <select
                        value={incident.status}
                        onChange={(event) => void change(incident, event.target.value)}
                        className="rounded border border-line p-1"
                      >
                        {statuses
                          .filter(
                            (status) =>
                              status === incident.status ||
                              (incident.status === "open" && ["in_progress", "discarded"].includes(status)) ||
                              (incident.status === "in_progress" && ["resolved", "discarded"].includes(status)),
                          )
                          .map((status) => (
                            <option key={status}>{status}</option>
                          ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function CsvAnalysis() {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<IncidentReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadSaved() {
      try {
        const response = await fetch(`${API}/analysis`, { headers: authHeaders() });
        if (response.status === 404) return;
        const payload = (await response.json().catch(() => ({}))) as IncidentReport & { detail?: unknown };
        if (!response.ok) throw Error(errorMessage(payload, "Unable to load the saved analysis."));
        if (!cancelled) setReport(payload);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load the saved analysis.");
      }
    }
    void loadSaved();
    return () => {
      cancelled = true;
    };
  }, []);

  function chooseFile(candidate?: File) {
    setError("");
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".csv")) {
      setError("Please choose a CSV file.");
      return;
    }
    setFile(candidate);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    chooseFile(event.dataTransfer.files[0]);
  }

  async function analyze() {
    if (!file) {
      setError("Choose a CSV file before analyzing.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${API}/analyze`, { method: "POST", headers: authHeaders(), body });
      const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
      if (!response.ok) throw Error(errorMessage(payload, `Analysis failed (${response.status}).`));
      setReport(payload as IncidentReport);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to analyze this file.");
    } finally {
      setLoading(false);
    }
  }

  async function downloadResults() {
    const response = await fetch(`${API}/results/export`, { headers: authHeaders() });
    if (!response.ok) {
      setError("Run an analysis before downloading results.");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "trackflow-incident-results.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div className="dashboard-card p-5">
        <label
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
          className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-line bg-panel-soft px-6 py-8 text-center hover:border-accent"
        >
          <span className="font-semibold text-foreground">Drop a CSV here or browse</span>
          <span className="mt-1 text-sm text-slate-600">
            Upload scripts/incidents-trackflow.csv. Only the latest aggregate report is saved.
          </span>
          <input type="file" accept=".csv,text/csv" onChange={onFileChange} className="sr-only" />
          {file ? (
            <span className="mt-3 rounded-full bg-accent-soft px-3 py-1 text-sm text-accent-strong">{file.name}</span>
          ) : null}
        </label>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void analyze()}
            disabled={loading}
            className="rounded-full bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-60"
          >
            {loading ? "Analyzing…" : "Analyze incidents"}
          </button>
          {report ? (
            <button
              type="button"
              onClick={() => void downloadResults()}
              className="rounded-full border border-line px-5 py-2 text-sm font-semibold text-foreground hover:bg-panel-soft"
            >
              Download Results CSV
            </button>
          ) : null}
        </div>
        {error ? (
          <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </p>
        ) : null}
      </div>
      {report ? (
        <>
          {report.filename ? (
            <p className="text-sm text-slate-600">
              Saved report from {report.filename}
              {report.analyzed_at ? ` · ${report.analyzed_at}` : ""}
            </p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-3">
            {(
              [
                ["Total records", report.total_records],
                ["Valid records", report.valid_records],
                ["Invalid records", report.invalid_records],
              ] as const
            ).map(([name, value]) => (
              <article key={name} className="dashboard-card p-5">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-600">{name}</p>
                <p className="metric-value mt-2 text-3xl font-semibold">{value}</p>
              </article>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Breakdown title="Category breakdown" counts={report.category_breakdown} percentages={report.category_percentages} />
            <Breakdown title="Status breakdown" counts={report.status_breakdown} percentages={report.status_percentages} />
            <Breakdown title="Country breakdown" counts={report.country_breakdown} percentages={report.country_percentages} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="dashboard-card p-5">
              <h2 className="font-display text-xl">Satisfaction</h2>
              <p className="mt-3 text-3xl font-semibold text-accent-strong">
                {report.average_satisfaction ?? "—"}
                <span className="ml-2 text-sm font-normal text-slate-600">average / 5</span>
              </p>
              <p className="mt-2 text-sm text-slate-600">
                Closed scored incidents: {report.closed_scored_incident_count}
              </p>
              <div className="mt-4 grid grid-cols-5 gap-2">
                {Object.entries(report.score_distribution).map(([score, count]) => (
                  <div key={score} className="rounded-lg bg-panel-soft p-2 text-center text-sm">
                    <strong>{score}</strong>
                    <br />
                    {count}
                  </div>
                ))}
              </div>
            </section>
            <section className="dashboard-card p-5">
              <h2 className="font-display text-xl">Invalid records by reason</h2>
              <div className="mt-4 space-y-2 text-sm">
                {Object.keys(report.invalid_by_reason).length === 0 ? (
                  <p className="text-slate-600">None</p>
                ) : (
                  Object.entries(report.invalid_by_reason).map(([reason, count]) => (
                    <div key={reason} className="flex justify-between rounded-lg bg-panel-soft px-3 py-2">
                      <span>{reason}</span>
                      <strong>{count}</strong>
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function IncidentsPage() {
  const [tab, setTab] = useState<Tab>("manager");

  return (
    <main className="space-y-6">
      <header className="rounded-2xl border border-accent/30 bg-accent-soft p-6">
        <p className="text-xs font-semibold uppercase tracking-[.2em] text-accent-strong">TrackFlow operations</p>
        <h1 className="mt-2 font-display text-4xl">
          {tab === "manager" ? "Centralized Incident Manager" : "TrackFlow — Incident Report Analysis"}
        </h1>
        <p className="mt-2 max-w-3xl text-sm">
          {tab === "manager"
            ? "Register, triage, and resolve incidents across every TrackFlow location."
            : "Upload an incident CSV to validate records and review aggregate trends without exposing customer information."}
        </p>
        <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Incident views">
          {(
            [
              ["manager", "Incident Manager"],
              ["analysis", "CSV Analysis"],
            ] as const
          ).map(([value, name]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
              className={`rounded-full px-4 py-1.5 text-sm font-semibold ${
                tab === value ? "bg-accent text-white" : "bg-panel text-slate-700 hover:bg-panel-soft"
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      </header>
      {tab === "manager" ? <IncidentManager /> : <CsvAnalysis />}
    </main>
  );
}
