"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { ApiError, apiRequest } from "@/lib/api-client";
import { clearToken, useIsAuthenticated } from "@/lib/auth";
import {
  acceptTokenSequence,
  accessTokenExpired,
  appliedSnapshotSequence,
  ChatMessageView,
  clearStoredSessionId,
  ConnectionState,
  GenerationCompleted,
  GenerationFailed,
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
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const sendRef = useRef<((event: string, data: Record<string, string>) => void) | null>(null);
  const seenSequence = useRef(0);
  const sessionRetry = useRef(false);
  const conversationGeneration = useRef(0);
  const authenticated = useIsAuthenticated();

  useEffect(() => {
    const token = currentAccessToken();
    if (!authenticated || !token) return undefined;
    if (accessTokenExpired(token)) {
      clearToken();
      return undefined;
    }
    const generation = conversationGeneration.current;
    let stopped = false;
    let chatHandle: { stop: () => void; send: (event: string, data: Record<string, string>) => void } | null = null;
    const stillCurrent = () => conversationGeneration.current === generation;

    async function openSession(): Promise<string | null> {
      const existing = readStoredSessionId();
      if (existing) return existing;
      const created = await apiRequest<ChatSessionResponse>("/chat/sessions", {
        method: "POST",
        auth: true,
        body: { client_id: "backoffice" },
      });
      if (!stillCurrent()) return null;
      storeSessionId(created.session_id);
      return created.session_id;
    }

    openSession()
      .then((id) => {
        if (stopped || !id || !stillCurrent()) return;
        setSessionId(id);
        chatHandle = startCxChat(id, token, {
          onConnectionChange: (state: ConnectionState, code?: number) => {
            if (!stillCurrent()) return;
            if (code === 4401) {
              setConnection("closed");
              setError("Your sign-in expired. Sign in again to use the chat.");
              clearToken();
              return;
            }
            if ((code === 4403 || code === 4404) && !sessionRetry.current) {
              sessionRetry.current = true;
              clearStoredSessionId();
              setConnection("connecting");
              setSessionAttempt((attempt) => attempt + 1);
              return;
            }
            if (code === 4403 || code === 4404) {
              setError("The support chat could not open a session.");
            }
            setConnection(state);
          },
          onSnapshot: (snapshot: SessionSnapshot) => {
            if (!stillCurrent()) return;
            seenSequence.current = appliedSnapshotSequence(snapshot.messages);
            setSessionId(snapshot.session_id);
            setMessages(snapshot.messages);
          },
          onUserMessage: (message: UserMessageEvent) => {
            if (!stillCurrent()) return;
            seenSequence.current = 0;
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
            if (!stillCurrent()) return;
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
            if (!stillCurrent()) return;
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
            if (!stillCurrent()) return;
            setError(null);
            setMessages((current) => {
              const next = current.map((item) => ({ ...item }));
              const matched = next.findIndex((item) => item.message_id === event.message_id);
              const index = matched >= 0 ? matched : lastGeneratingIndex(next);
              if (index < 0) return current;
              next[index] = { ...next[index], message_id: event.message_id, status: "complete" };
              return next;
            });
          },
          onFailed: (event: GenerationFailed) => {
            if (!stillCurrent()) return;
            setError(event.message);
            setMessages((current) => {
              const next = current.map((item) => ({ ...item }));
              const matched = next.findIndex((item) => item.message_id === event.message_id);
              const index = matched >= 0 ? matched : lastGeneratingIndex(next);
              const failed: ChatMessageView = {
                message_id: event.message_id,
                role: "assistant",
                text: event.message,
                status: "failed",
              };
              if (index < 0) return [...next, failed];
              next[index] = { ...next[index], ...failed };
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
        if (!stillCurrent()) return;
        setError(requestError instanceof ApiError ? requestError.message : "The support chat could not start.");
        setConnection("closed");
      });

    return () => {
      stopped = true;
      sendRef.current = null;
      chatHandle?.stop();
    };
  }, [authenticated, sessionAttempt]);

  const generating = messages.some((message) => message.role === "assistant" && message.status === "generating");

  function sendDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !sessionId || !sendRef.current) return;
    setError(null);
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

  function startNewConversation() {
    conversationGeneration.current += 1;
    clearStoredSessionId();
    seenSequence.current = 0;
    sessionRetry.current = false;
    setSessionId(null);
    setMessages([]);
    setDraft("");
    setError(null);
    setConnection("connecting");
    setSessionAttempt((attempt) => attempt + 1);
  }

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-strong">
              TrackFlow account support
            </p>
            <h2 className="mt-1 font-display text-2xl text-foreground">First-line CX</h2>
          </div>
          <button
            type="button"
            onClick={startNewConversation}
            disabled={connection === "connecting"}
            className="rounded-full border border-line px-5 py-2.5 text-sm font-semibold text-foreground disabled:cursor-not-allowed disabled:opacity-60"
          >
            New conversation
          </button>
        </div>
        <p className="mt-2 max-w-2xl text-sm text-slate-700">
          Ask about tracking, returns, and delivery. The answer appears as it is generated. Sending
          another question, or Stop, interrupts the current answer and keeps that partial reply.
        </p>
        <p className="mt-3 text-xs text-slate-600" role="status">
          {connection === "open"
            ? "Connected"
            : connection === "reconnecting"
              ? "Reconnecting…"
              : connection === "closed"
                ? "Not connected"
                : "Connecting…"}
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
              className="rounded-xl border border-line bg-panel p-4 dark:border-slate-600 dark:bg-slate-900"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                {message.role === "user" ? "You" : "TrackFlow"}
                {message.status === "interrupted" ? " · Interrupted" : ""}
                {message.status === "generating" ? " · Writing" : ""}
                {message.status === "failed" ? " · Failed" : ""}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-foreground dark:text-slate-100">
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
