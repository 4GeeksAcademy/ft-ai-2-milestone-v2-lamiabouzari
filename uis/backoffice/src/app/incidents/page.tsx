"use client";

import { ChangeEvent, DragEvent, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { ApiError } from "@/lib/api-client";

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
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "/api/backend").replace(/\/$/, "");

function Breakdown({ title, counts, percentages }: { title: string; counts: Record<string, number>; percentages?: Record<string, number> }) {
  return (
    <section className="dashboard-card p-5">
      <h2 className="font-display text-xl text-foreground">{title}</h2>
      <div className="mt-4 space-y-3">
        {Object.entries(counts).map(([label, count]) => (
          <div key={label}>
            <div className="flex justify-between gap-3 text-sm"><span>{label}</span><strong>{count}{percentages ? ` · ${percentages[label]}%` : ""}</strong></div>
            <div className="mt-1 h-2 rounded-full bg-panel-soft"><div className="h-2 rounded-full bg-accent" style={{ width: `${percentages?.[label] ?? 0}%` }} /></div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function IncidentsPage() {
  return (
    <RequireAuth>
      <IncidentsPageContent />
    </RequireAuth>
  );
}

function IncidentsPageContent() {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<IncidentReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function chooseFile(candidate?: File) {
    setError("");
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".csv")) {
      setError("Please choose a CSV file.");
      return;
    }
    setFile(candidate);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) { chooseFile(event.target.files?.[0]); }
  function onDrop(event: DragEvent<HTMLLabelElement>) { event.preventDefault(); chooseFile(event.dataTransfer.files[0]); }

  async function analyze() {
    if (!file) { setError("Choose a CSV file before analyzing."); return; }
    setLoading(true); setError("");
    try {
      const body = new FormData(); body.append("file", file);
      const response = await fetch(`${API_BASE}/api/incidents/analyze`, { method: "POST", body });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new ApiError(payload.detail || `Analysis failed (${response.status}).`, response.status);
      }
      setReport((await response.json()) as IncidentReport);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to analyze this file.");
    } finally { setLoading(false); }
  }

  async function downloadResults() {
    const response = await fetch(`${API_BASE}/api/incidents/results/export`);
    if (!response.ok) { setError("Run an analysis before downloading results."); return; }
    const blob = await response.blob(); const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = "trackflow-incident-results.csv"; link.click(); URL.revokeObjectURL(url);
  }

  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-accent/30 bg-accent-soft p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-strong">TrackFlow operations</p>
        <h1 className="mt-2 font-display text-3xl text-foreground sm:text-4xl">TrackFlow — Incident Report Analysis</h1>
        <p className="mt-3 max-w-3xl text-sm text-slate-700">Upload an incident CSV to validate records and review aggregate trends without exposing customer information.</p>
      </div>
      <div className="dashboard-card p-5">
        <label onDragOver={(event) => event.preventDefault()} onDrop={onDrop} className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-line bg-panel-soft px-6 py-8 text-center hover:border-accent">
          <span className="font-semibold text-foreground">Drop a CSV here or browse</span><span className="mt-1 text-sm text-slate-600">Only aggregate results are retained.</span>
          <input type="file" accept=".csv,text/csv" onChange={onFileChange} className="sr-only" />
          {file ? <span className="mt-3 rounded-full bg-accent-soft px-3 py-1 text-sm text-accent-strong">{file.name}</span> : null}
        </label>
        <div className="mt-4 flex flex-wrap items-center gap-3"><button type="button" onClick={analyze} disabled={loading} className="rounded-full bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-60">{loading ? "Analyzing…" : "Analyze incidents"}</button>{report ? <button type="button" onClick={downloadResults} className="rounded-full border border-line px-5 py-2 text-sm font-semibold text-foreground hover:bg-panel-soft">Download Results CSV</button> : null}</div>
        {error ? <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
      </div>
      {report ? <>
        <div className="grid gap-4 sm:grid-cols-3">{[["Total records", report.total_records], ["Valid records", report.valid_records], ["Invalid records", report.invalid_records]].map(([label, value]) => <article key={label} className="dashboard-card p-5"><p className="text-xs uppercase tracking-[0.16em] text-slate-600">{label}</p><p className="metric-value mt-2 text-3xl font-semibold">{value}</p></article>)}</div>
        <div className="grid gap-4 lg:grid-cols-3"><Breakdown title="Category breakdown" counts={report.category_breakdown} percentages={report.category_percentages} /><Breakdown title="Status breakdown" counts={report.status_breakdown} percentages={report.status_percentages} /><Breakdown title="Country breakdown" counts={report.country_breakdown} percentages={report.country_percentages} /></div>
        <div className="grid gap-4 lg:grid-cols-2"><section className="dashboard-card p-5"><h2 className="font-display text-xl">Satisfaction</h2><p className="mt-3 text-3xl font-semibold text-accent-strong">{report.average_satisfaction ?? "—"}<span className="ml-2 text-sm font-normal text-slate-600">average / 5</span></p><p className="mt-2 text-sm text-slate-600">Closed scored incidents: {report.closed_scored_incident_count}</p><div className="mt-4 grid grid-cols-5 gap-2">{Object.entries(report.score_distribution).map(([score, count]) => <div key={score} className="rounded-lg bg-panel-soft p-2 text-center text-sm"><strong>{score}</strong><br />{count}</div>)}</div></section><section className="dashboard-card p-5"><h2 className="font-display text-xl">Invalid records by reason</h2><div className="mt-4 space-y-2 text-sm">{Object.entries(report.invalid_by_reason).map(([reason, count]) => <div key={reason} className="flex justify-between rounded-lg bg-panel-soft px-3 py-2"><span>{reason}</span><strong>{count}</strong></div>)}</div></section></div>
      </> : null}
    </section>
  );
}