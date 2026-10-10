"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { ApiError, apiRequest, apiUpload } from "@/lib/api-client";
import { clearToken } from "@/lib/auth";
import { applyRfpCreated, RfpCreatedEvent, startRfpEventStream } from "@/lib/rfp-events";

interface RfpSection {
  department_key: string;
  department_name: string;
  contact: string;
  key_aspects: string[];
  open_questions: string[];
  draft_content?: string;
  approval_status?: string | null;
  iteration_count?: number;
  evaluation_results?: { overall_pass?: boolean; iterations?: number } | null;
}

interface RfpApproval {
  thread_id: string;
  department_id: string;
  department_name: string | null;
  owner: string | null;
  draft_content: string;
  evaluation_results: { overall_pass?: boolean; iterations?: number } | null;
  iteration_count: number;
  approval_status: string;
  interrupted: boolean;
  actions: string[];
}

interface RfpTicket {
  ticket_id: string;
  rfp_id?: string | null;
  status: string;
  source_filename: string;
  discard_reason: string | null;
  error_message: string | null;
  intake_failed: boolean;
  currency_context: string | null;
  handoff_ready: boolean;
  part3_handoff_ready?: boolean;
  approvals?: RfpApproval[];
  open_conflicts?: { conflict_id: string; arbiter: string; next: string; resolution_rule: string }[];
  final_document?: { document_markdown: string } | null;
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

function ticketFromEvent(event: RfpCreatedEvent): RfpTicket {
  return {
    ticket_id: event.ticket_id,
    status: event.status,
    source_filename: event.client_name,
    discard_reason: null,
    error_message: null,
    intake_failed: false,
    currency_context: null,
    handoff_ready: false,
    metadata: {
      client_name: event.client_name,
      client_country: event.client_country,
      services_requested: event.services_requested,
      monthly_volume: null,
      deadline: null,
      budget_range: null,
      departments_needed: [],
      readability: {},
      document_style: "",
    },
    sections: [],
    synthesizer: null,
  };
}

function RfpIntakeContent() {
  const [tickets, setTickets] = useState<RfpTicket[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState<Record<string, { comment: string; changes: string }>>({});
  const [notice, setNotice] = useState<RfpCreatedEvent | null>(null);
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());
  const ticketsRef = useRef<RfpTicket[]>([]);

  function replaceTickets(next: RfpTicket[]) {
    ticketsRef.current = next;
    setTickets(next);
  }

  async function refresh() {
    const rows = await apiRequest<RfpTicket[]>("/rfp/tickets", { auth: true, cache: "no-store" });
    replaceTickets(rows);
    setListError(null);
  }

  useEffect(() => {
    let cancelled = false;
    apiRequest<RfpTicket[]>("/rfp/tickets", { auth: true, cache: "no-store" })
      .then((rows) => {
        if (cancelled) return;
        if (!Array.isArray(rows)) throw new Error("Ticket list was not a list.");
        replaceTickets(rows);
        setListError(null);
      })
      .catch((requestError: unknown) => {
        if (cancelled) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          clearToken();
          return;
        }
        setListError(
          requestError instanceof ApiError ? requestError.message : "Saved tickets could not be loaded."
        );
      })
      .finally(() => {
        if (!cancelled) setLoadingList(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const stop = startRfpEventStream<RfpTicket>({
      fetchTickets: () => apiRequest<RfpTicket[]>("/rfp/tickets", { auth: true, cache: "no-store" }),
      currentTickets: () => ticketsRef.current,
      onTickets: (next, announced) => {
        replaceTickets(next);
        if (announced.length > 0) {
          const newest = announced[0];
          setHighlighted((current) => new Set(current).add(newest.ticket_id));
          if (newest.metadata?.client_name && newest.metadata.client_country) {
            setNotice({
              ticket_id: newest.ticket_id,
              rfp_id: newest.rfp_id ?? null,
              client_name: newest.metadata.client_name,
              client_country: newest.metadata.client_country,
              services_requested: newest.metadata.services_requested,
              status: newest.status,
              created_at: "",
            });
          }
        }
      },
      onCreated: (event) => {
        const existing = ticketsRef.current.find((ticket) => ticket.ticket_id === event.ticket_id);
        const applied = applyRfpCreated(ticketsRef.current, event, ticketFromEvent(event));
        const next = applied.added
          ? applied.tickets
          : applied.tickets.map((ticket) => {
              if (ticket.ticket_id !== event.ticket_id || ticket.metadata?.client_name) return ticket;
              const shell = ticketFromEvent(event);
              return { ...ticket, metadata: shell.metadata };
            });
        replaceTickets(next);
        if (!applied.added && existing?.metadata?.client_name) return;
        setHighlighted((current) => new Set(current).add(event.ticket_id));
        setNotice(event);
      },
    });
    return stop;
  }, []);

  const stillAnalyzing = tickets.some(
    (ticket) => ticket.status === "analyzing" && !ticket.intake_failed && !ticket.error_message
  );

  useEffect(() => {
    if (!stillAnalyzing) return undefined;
    const timer = window.setInterval(() => {
      void apiRequest<RfpTicket[]>("/rfp/tickets", { auth: true, cache: "no-store" })
        .then((rows) => {
          ticketsRef.current = rows;
          setTickets(rows);
          setListError(null);
        })
        .catch(() => {
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

      {loadingList ? <p className="text-sm text-slate-600">Loading saved tickets…</p> : null}
      {listError ? (
        <p role="alert" className="text-sm text-red-800">
          {listError}
        </p>
      ) : null}
      {!loadingList && !listError && tickets.length === 0 ? (
        <p className="text-sm text-slate-600">No saved RFP tickets.</p>
      ) : null}

      {notice ? (
        <p role="status" className="rounded-xl border border-accent bg-white px-4 py-3 text-sm text-foreground">
          New RFP from {notice.client_name} ({notice.client_country}). Services: {(notice.services_requested ?? []).join(", ")}.
        </p>
      ) : null}

      {tickets.map((ticket) => (
        <article
          key={ticket.ticket_id}
          className={
            highlighted.has(ticket.ticket_id)
              ? "dashboard-card p-6 ring-2 ring-accent"
              : "dashboard-card p-6"
          }
        >
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
                  {ticket.metadata.readability?.word_count ?? "—"} words, Flesch{" "}
                  {ticket.metadata.readability?.flesch_reading_ease ?? "—"}
                </dd>
              </div>
            </dl>
          ) : null}
          {(ticket.sections ?? []).length > 0 ? (
            <ul className="mt-4 space-y-3">
              {(ticket.sections ?? []).map((section) => (
                <li key={section.department_key} className="rounded-xl bg-panel-soft p-4 text-sm">
                  <p className="font-semibold text-foreground">
                    {section.department_name} — {section.contact}
                  </p>
                  <p className="mt-1 text-slate-700">{(section.key_aspects ?? []).join(" ")}</p>
                  {(section.open_questions ?? []).length > 0 ? (
                    <p className="mt-2 text-slate-600">Ask: {(section.open_questions ?? []).join(" ")}</p>
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
          {ticket.part3_handoff_ready &&
          (ticket.status === "under_evaluation" || ticket.status === "needs_human_review") ? (
            <button
              type="button"
              className="mt-4 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white"
              onClick={() =>
                apiRequest(`/rfp/tickets/${ticket.ticket_id}/approval`, { method: "POST", auth: true })
                  .then(() => refresh())
                  .catch((requestError: unknown) =>
                    setError(requestError instanceof ApiError ? requestError.message : "Could not open approval.")
                  )
              }
            >
              Start approval
            </button>
          ) : null}
          {(ticket.approvals ?? []).length > 0 ? (
            <div className="mt-4 space-y-3">
              {(ticket.open_conflicts ?? []).map((conflict) => (
                <p key={conflict.conflict_id} className="text-sm text-red-800">
                  {conflict.conflict_id}: {conflict.arbiter}. {conflict.resolution_rule} Next: {conflict.next}
                </p>
              ))}
              {(ticket.open_conflicts ?? []).length > 0 ? (
                <button
                  type="button"
                  className="rounded-full border border-slate-300 px-4 py-2 text-sm"
                  onClick={() =>
                    apiRequest(`/rfp/tickets/${ticket.ticket_id}/arbitration`, { method: "POST", auth: true })
                      .then(() => refresh())
                      .catch((requestError: unknown) =>
                        setError(requestError instanceof ApiError ? requestError.message : "Arbitration failed.")
                      )
                  }
                >
                  Apply arbitration
                </button>
              ) : null}
              {(ticket.approvals ?? []).map((approval) => {
                const noteKey = `${ticket.ticket_id}:${approval.department_id}`;
                const note = notes[noteKey] ?? { comment: "", changes: "" };
                async function decide(decision: "approve" | "reject" | "request_changes") {
                  try {
                    await apiRequest(`/rfp/tickets/${ticket.ticket_id}/approval/resume`, {
                      method: "POST",
                      auth: true,
                      body: {
                        department: approval.department_id,
                        decision,
                        actor: approval.owner,
                        comment: note.comment,
                        requested_changes: decision === "request_changes" ? note.changes : null,
                      },
                    });
                    await refresh();
                  } catch (requestError: unknown) {
                    setError(requestError instanceof ApiError ? requestError.message : "Approval failed.");
                  }
                }
                return (
                  <section key={approval.thread_id} className="rounded-xl bg-panel-soft p-4 text-sm">
                    <p className="font-semibold text-foreground">
                      {approval.department_name} — {approval.owner}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                      {approval.approval_status}
                      {approval.interrupted ? " · waiting for this owner" : ""} · iteration {approval.iteration_count}
                      {approval.evaluation_results?.overall_pass === false ? " · evaluation failed" : ""}
                    </p>
                    <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-slate-800">
                      {approval.draft_content}
                    </pre>
                    {approval.actions.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        <label className="block text-xs text-slate-600">
                          Comment
                          <input
                            value={note.comment}
                            onChange={(event) =>
                              setNotes((current) => ({ ...current, [noteKey]: { ...note, comment: event.target.value } }))
                            }
                            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                          />
                        </label>
                        <label className="block text-xs text-slate-600">
                          Requested changes
                          <textarea
                            value={note.changes}
                            onChange={(event) =>
                              setNotes((current) => ({ ...current, [noteKey]: { ...note, changes: event.target.value } }))
                            }
                            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                          />
                        </label>
                        <div className="flex flex-wrap gap-2">
                          <button type="button" className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white" onClick={() => decide("approve")}>
                            Approve
                          </button>
                          <button type="button" className="rounded-full border border-slate-300 px-4 py-2 text-sm" onClick={() => decide("reject")}>
                            Reject
                          </button>
                          <button type="button" className="rounded-full border border-slate-300 px-4 py-2 text-sm" onClick={() => decide("request_changes")}>
                            Request changes
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </section>
                );
              })}
            </div>
          ) : null}
          {ticket.final_document ? (
            <div className="mt-4">
              <p className="text-sm font-semibold text-foreground">
                Final document · /rfp/tickets/{ticket.ticket_id}/document
              </p>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-sm text-slate-800">
                {ticket.final_document.document_markdown}
              </pre>
            </div>
          ) : null}
        </article>
      ))}
    </section>
  );
}
