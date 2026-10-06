"use client";

import { FormEvent, useEffect, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { ApiError, apiRequest, apiUpload } from "@/lib/api-client";

interface RfpSection {
  department_key: string;
  department_name: string;
  contact: string;
  key_aspects: string[];
  open_questions: string[];
}

interface RfpTicket {
  ticket_id: string;
  status: "analyzing" | "intake_complete" | "discarded";
  source_filename: string;
  discard_reason: string | null;
  error_message: string | null;
  intake_failed: boolean;
  currency_context: string | null;
  handoff_ready: boolean;
  metadata: {
    client_name: string | null;
    client_country: string | null;
    services_requested: string[];
    monthly_volume: string | null;
    deadline: string | null;
    budget_range: string | null;
    departments_needed: string[];
    readability: Record<string, number>;
    document_style: string;
  } | null;
  sections: RfpSection[];
  synthesizer: { sales_summary: string } | null;
}

export default function RfpIntakePage() {
  return (
    <RequireAuth>
      <RfpIntakeContent />
    </RequireAuth>
  );
}

function RfpIntakeContent() {
  const [tickets, setTickets] = useState<RfpTicket[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  async function refresh() {
    const rows = await apiRequest<RfpTicket[]>("/rfp/tickets", { auth: true });
    setTickets(rows);
  }

  useEffect(() => {
    let cancelled = false;
    refresh().catch((requestError: unknown) => {
      if (!cancelled) {
        setError(requestError instanceof ApiError ? requestError.message : "Could not load RFP tickets.");
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const stillAnalyzing = tickets.some(
    (ticket) => ticket.status === "analyzing" && !ticket.intake_failed && !ticket.error_message
  );

  useEffect(() => {
    if (!stillAnalyzing) return undefined;
    const timer = window.setInterval(() => {
      refresh().catch(() => {
        // Keep the last successful list while a refresh fails.
      });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [stillAnalyzing]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await apiUpload<{ ticket_id: string; status: string }>("/rfp/tickets", file);
      setFile(null);
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-strong">
          TrackFlow Sales
        </p>
        <h2 className="mt-1 font-display text-2xl text-foreground">RFP intake</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-700">
          Upload one client PDF. The ticket stays in analyzing until intake finishes, then shows
          the departments Sales should contact.
        </p>
        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            type="file"
            accept="application/pdf,.pdf"
            aria-label="RFP PDF"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="text-sm text-slate-700"
          />
          <button
            type="submit"
            disabled={uploading || !file}
            className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {uploading ? "Uploading…" : "Upload PDF"}
          </button>
        </form>
        {error ? (
          <p role="alert" className="mt-4 text-sm text-red-800">
            {error}
          </p>
        ) : null}
      </div>

      {tickets.map((ticket) => (
        <article key={ticket.ticket_id} className="dashboard-card p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-display text-lg text-foreground">{ticket.source_filename}</h3>
            <p className="text-xs font-semibold uppercase tracking-wide text-accent-strong">
              {ticket.intake_failed || ticket.error_message ? "intake failed" : ticket.status}
            </p>
          </div>
          <p className="mt-1 text-xs text-slate-500">{ticket.ticket_id}</p>
          {ticket.intake_failed || ticket.error_message ? (
            <p role="alert" className="mt-4 text-sm text-red-800">
              Intake failed and is not still analyzing. {ticket.error_message}
            </p>
          ) : ticket.status === "analyzing" ? (
            <p role="status" className="mt-4 text-sm text-slate-700">
              Reading the PDF and routing departments…
            </p>
          ) : null}
          {ticket.status === "discarded" ? (
            <p className="mt-4 text-sm text-slate-700">{ticket.discard_reason}</p>
          ) : null}
          {ticket.metadata ? (
            <dl className="mt-4 grid gap-2 text-sm text-slate-800 sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase text-slate-500">Client</dt>
                <dd>{ticket.metadata.client_name || "Not stated"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Country</dt>
                <dd>
                  {ticket.metadata.client_country || "Not stated"}
                  {ticket.currency_context ? ` · ${ticket.currency_context}` : ""}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Monthly volume</dt>
                <dd>{ticket.metadata.monthly_volume || "Not stated"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-slate-500">Readability</dt>
                <dd>
                  {ticket.metadata.readability.word_count ?? "—"} words, Flesch{" "}
                  {ticket.metadata.readability.flesch_reading_ease ?? "—"}
                </dd>
              </div>
            </dl>
          ) : null}
          {ticket.sections.length > 0 ? (
            <ul className="mt-4 space-y-3">
              {ticket.sections.map((section) => (
                <li key={section.department_key} className="rounded-xl bg-panel-soft p-4 text-sm">
                  <p className="font-semibold text-foreground">
                    {section.department_name} — {section.contact}
                  </p>
                  <p className="mt-1 text-slate-700">{section.key_aspects.join(" ")}</p>
                  {section.open_questions.length > 0 ? (
                    <p className="mt-2 text-slate-600">Ask: {section.open_questions.join(" ")}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {ticket.synthesizer ? (
            <pre className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-800">
              {ticket.synthesizer.sales_summary}
            </pre>
          ) : null}
        </article>
      ))}
    </section>
  );
}
