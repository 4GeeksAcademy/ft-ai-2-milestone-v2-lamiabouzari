"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { ApiError, apiRequest } from "@/lib/api-client";
import {
  acceptTokenSequence,
  appliedSnapshotSequence,
  ChatMessageView,
  ConnectionState,
  GenerationCompleted,
  GenerationInterrupted,
  SessionSnapshot,
  TokenChunk,
  UserMessageEvent,
  currentAccessToken,
  readStoredSessionId,
  startCxChat,
  storeSessionId,
} from "@/lib/cx-chat";

interface ChatSessionResponse {
  session_id: string;
  agent_id: string;
  status: string;
}

function lastGeneratingIndex(messages: ChatMessageView[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "assistant" && message.status === "generating") return index;
  }
  return -1;
}

function SupportChat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [draft, setDraft] = useState("");
  const [connection, setConnection] = useState<ConnectionState | "connecting">("connecting");
  const [error, setError] = useState<string | null>(null);
  const sendRef = useRef<((event: string, data: Record<string, string>) => void) | null>(null);
  const seenSequence = useRef(0);

  useEffect(() => {
    const token = currentAccessToken();
    if (!token) return undefined;
    let stopped = false;
    let chatHandle: { stop: () => void; send: (event: string, data: Record<string, string>) => void } | null = null;

    async function openSession(): Promise<string | null> {
      const existing = readStoredSessionId();
      if (existing) return existing;
      const created = await apiRequest<ChatSessionResponse>("/chat/sessions", {
        method: "POST",
        auth: true,
        body: { client_id: "backoffice" },
      });
      storeSessionId(created.session_id);
      return created.session_id;
    }

    openSession()
      .then((id) => {
        if (stopped || !id) return;
        setSessionId(id);
        chatHandle = startCxChat(id, token, {
          onConnectionChange: (state: ConnectionState) => setConnection(state),
          onSnapshot: (snapshot: SessionSnapshot) => {
            seenSequence.current = appliedSnapshotSequence(snapshot.messages);
            setSessionId(snapshot.session_id);
            setMessages(snapshot.messages);
          },
          onUserMessage: (message: UserMessageEvent) => {
            setMessages((current) => {
              if (current.some((item) => item.message_id === message.message_id)) return current;
              return [
                ...current,
                {
                  message_id: message.message_id,
                  role: "user",
                  text: message.text,
                  status: "complete",
                },
              ];
            });
          },
          onToken: (chunk: TokenChunk) => {
            if (!acceptTokenSequence(seenSequence.current, chunk.sequence)) return;
            seenSequence.current = chunk.sequence;
            setMessages((current) => {
              const next = current.map((item) => ({ ...item }));
              const index = lastGeneratingIndex(next);
              if (index >= 0) {
                next[index] = { ...next[index], text: next[index].text + chunk.token };
                return next;
              }
              next.push({
                message_id: "",
                role: "assistant",
                text: chunk.token,
                status: "generating",
              });
              return next;
            });
          },
          onInterrupted: (event: GenerationInterrupted) => {
            setMessages((current) => {
              const next = current.map((item) => ({ ...item }));
              const matched = next.findIndex((item) => item.message_id === event.message_id);
              const index = matched >= 0 ? matched : lastGeneratingIndex(next);
              if (index < 0) return current;
              next[index] = { ...next[index], message_id: event.message_id, status: "interrupted" };
              return next;
            });
          },
          onCompleted: (event: GenerationCompleted) => {
            setMessages((current) => {
              const next = current.map((item) => ({ ...item }));
              const matched = next.findIndex((item) => item.message_id === event.message_id);
              const index = matched >= 0 ? matched : lastGeneratingIndex(next);
              if (index < 0) return current;
              next[index] = { ...next[index], message_id: event.message_id, status: "complete" };
              return next;
            });
          },
        });
        if (stopped) {
          chatHandle.stop();
          return;
        }
        sendRef.current = chatHandle.send;
      })
      .catch((requestError: unknown) => {
        setError(requestError instanceof ApiError ? requestError.message : "The support chat could not start.");
        setConnection("closed");
      });

    return () => {
      stopped = true;
      sendRef.current = null;
      chatHandle?.stop();
    };
  }, []);

  const generating = messages.some((message) => message.role === "assistant" && message.status === "generating");

  function sendDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !sessionId || !sendRef.current) return;
    if (generating) {
      sendRef.current("interrupt_requested", { session_id: sessionId, new_input: text });
    } else {
      sendRef.current("user_message", { session_id: sessionId, text });
    }
    setDraft("");
  }

  function stopGeneration() {
    if (!sessionId || !sendRef.current) return;
    sendRef.current("interrupt_requested", { session_id: sessionId, new_input: "" });
  }

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-strong">
          TrackFlow account support
        </p>
        <h2 className="mt-1 font-display text-2xl text-foreground">First-line CX</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-700">
          Ask about tracking, returns, and delivery. The answer appears as it is generated. Sending
          another question, or Stop, interrupts the current answer and keeps that partial reply.
        </p>
        <p className="mt-3 text-xs text-slate-600" role="status">
          {connection === "open" ? "Connected" : connection === "reconnecting" ? "Reconnecting…" : "Connecting…"}
        </p>

        <div className="mt-6 space-y-3" aria-live="polite">
          {messages.length === 0 ? (
            <p className="rounded-xl bg-panel-soft p-4 text-sm text-slate-700">
              No messages yet. Ask where an order is, or about a return.
            </p>
          ) : null}
          {messages.map((message, index) => (
            <article
              key={message.message_id || `${message.role}-${index}`}
              className="rounded-xl border border-line bg-panel p-4"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {message.role === "user" ? "You" : "TrackFlow"}
                {message.status === "interrupted" ? " · Interrupted" : ""}
                {message.status === "generating" ? " · Writing" : ""}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">
                {message.text}
              </p>
            </article>
          ))}
        </div>

        {error ? (
          <div role="alert" className="mt-6 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900">
            {error}
          </div>
        ) : null}

        <form onSubmit={sendDraft} className="mt-6 space-y-3">
          <label htmlFor="cx-message" className="block text-sm font-semibold text-foreground">
            Message
          </label>
          <textarea
            id="cx-message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={2000}
            rows={3}
            placeholder="Where is my order?"
            className="w-full rounded-xl border border-line bg-panel px-4 py-3 text-sm text-foreground placeholder:text-slate-500"
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-slate-600">Do not share customer personal or sensitive data.</p>
            <div className="flex gap-2">
              {generating ? (
                <button
                  type="button"
                  onClick={stopGeneration}
                  className="rounded-full border border-line px-5 py-2.5 text-sm font-semibold text-foreground"
                >
                  Stop
                </button>
              ) : null}
              <button
                type="submit"
                disabled={!draft.trim() || connection !== "open"}
                className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
              >
                {generating ? "Send and interrupt" : "Send"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </section>
  );
}

export default function KnowledgePage() {
  return (
    <RequireAuth>
      <SupportChat />
    </RequireAuth>
  );
}
