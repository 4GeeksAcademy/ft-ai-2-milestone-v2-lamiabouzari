"use client";

import { FormEvent, useState } from "react";
import { ApiError, apiRequest } from "@/lib/api-client";

interface KnowledgeResponse {
  answer: string;
}

export default function KnowledgePage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const response = await apiRequest<KnowledgeResponse>("/knowledge/query", {
        method: "POST",
        body: { question: question.trim() },
      });
      setAnswer(response.answer);
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "We could not reach the knowledge service. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-strong">
          TrackFlow account support
        </p>
        <h2 className="mt-1 font-display text-2xl text-foreground">Knowledge base</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-700">
          Ask about delivery service levels, returns, carrier coverage, or storage pricing. Answers
          are grounded in the approved TrackFlow reference documents.
        </p>

        <form onSubmit={submitQuestion} className="mt-6 space-y-3">
          <label htmlFor="knowledge-question" className="block text-sm font-semibold text-foreground">
            Client question
          </label>
          <textarea
            id="knowledge-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={2000}
            rows={4}
            placeholder="For example: Can we guarantee delivery during Black Friday?"
            className="w-full rounded-xl border border-line bg-panel px-4 py-3 text-sm text-foreground placeholder:text-slate-500"
            required
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-slate-600">Do not share customer personal or sensitive data.</p>
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Searching…" : "Ask TrackFlow"}
            </button>
          </div>
        </form>

        {loading ? (
          <p role="status" aria-live="polite" className="mt-6 rounded-xl bg-panel-soft p-4 text-sm text-slate-700">
            Checking the TrackFlow knowledge base…
          </p>
        ) : null}
        {error ? (
          <div role="alert" className="mt-6 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-100">
            <p className="font-semibold">We could not answer your question.</p>
            <p className="mt-1">{error}</p>
          </div>
        ) : null}
        {answer ? (
          <div className="mt-6 rounded-xl border border-line bg-panel p-5" aria-live="polite">
            <h3 className="font-display text-lg text-foreground">Suggested client response</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">{answer}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
