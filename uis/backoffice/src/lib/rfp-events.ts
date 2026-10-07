import { getToken } from "@/lib/auth";

export interface RfpCreatedEvent {
  ticket_id: string;
  rfp_id: string | null;
  client_name: string;
  client_country: string;
  services_requested: string[];
  status: string;
  created_at: string;
}

export interface SseFrame {
  id?: string;
  event?: string;
  data?: string;
  comment?: string;
}

interface TicketIdentity {
  ticket_id: string;
}

export function nextBackoffMs(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, 30_000);
}

export function mergeRecoveredTickets<T extends TicketIdentity>(
  current: T[],
  incoming: T[]
): { tickets: T[]; added: T[] } {
  const known = new Set(current.map((ticket) => ticket.ticket_id));
  const incomingIds = new Set(incoming.map((ticket) => ticket.ticket_id));
  const localOnly = current.filter((ticket) => !incomingIds.has(ticket.ticket_id));
  const added = incoming.filter((ticket) => !known.has(ticket.ticket_id));
  return { tickets: [...incoming, ...localOnly], added };
}

export function applyRfpCreated<T extends TicketIdentity>(
  current: T[],
  event: RfpCreatedEvent,
  created: T
): { tickets: T[]; added: boolean } {
  if (current.some((ticket) => ticket.ticket_id === event.ticket_id)) {
    // Keep the stored row, including a later status. Do not apply event.status.
    return { tickets: current, added: false };
  }
  return { tickets: [created, ...current], added: true };
}

export function parseSseBuffer(buffer: string): { frames: SseFrame[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  const frames = parts.map(parseFrame).filter((frame): frame is SseFrame => frame !== null);
  return { frames, rest };
}

function parseFrame(block: string): SseFrame | null {
  const frame: SseFrame = {};
  const dataLines: string[] = [];
  const comments: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) {
      if (line.startsWith(":")) comments.push(line.slice(1).trim());
      continue;
    }
    const separator = line.indexOf(":");
    if (separator < 0) continue;
    const field = line.slice(0, separator);
    const value = line.slice(separator + 1).replace(/^ /, "");
    if (field === "event") frame.event = value;
    else if (field === "data") dataLines.push(value);
    else if (field === "id") frame.id = value;
  }
  if (dataLines.length > 0) frame.data = dataLines.join("\n");
  if (comments.length > 0) frame.comment = comments.join("\n");
  if (!frame.event && !frame.data && !frame.id && !frame.comment) return null;
  return frame;
}

function apiBaseUrl(): string {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "/api/backend";
  return apiBaseUrl.replace(/\/$/, "");
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    const finish = () => {
      clearTimeout(timer);
      resolve();
    };
    if (signal.aborted) {
      finish();
      return;
    }
    signal.addEventListener("abort", finish, { once: true });
  });
}

export function startRfpEventStream<T extends TicketIdentity>(options: {
  fetchTickets: () => Promise<T[]>;
  currentTickets: () => T[];
  onTickets: (tickets: T[], announced: T[]) => void;
  onCreated: (event: RfpCreatedEvent) => void;
}): () => void {
  const controller = new AbortController();
  const { signal } = controller;

  async function readBody(body: ReadableStream<Uint8Array>): Promise<void> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (!signal.aborted) {
        const { done, value } = await reader.read();
        if (done) return;
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSseBuffer(buffer);
        buffer = parsed.rest;
        for (const frame of parsed.frames) {
          if (frame.comment && !frame.event) continue;
          if (frame.event !== "rfp_ticket_created" || !frame.data) continue;
          options.onCreated(JSON.parse(frame.data) as RfpCreatedEvent);
        }
      }
    } finally {
      await reader.cancel().catch(() => undefined);
    }
  }

  async function loop(): Promise<void> {
    let attempt = 0;
    let reconnecting = false;
    while (!signal.aborted) {
      try {
        const incoming = await options.fetchTickets();
        if (signal.aborted) return;
        const recovered = mergeRecoveredTickets(options.currentTickets(), incoming);
        options.onTickets(recovered.tickets, reconnecting ? recovered.added : []);
        reconnecting = true;
        const token = getToken();
        const response = await fetch(`${apiBaseUrl()}/events/stream`, {
          headers: {
            Accept: "text/event-stream",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          signal,
        });
        if (!response.ok || !response.body) {
          throw new Error(`SSE failed with status ${response.status}`);
        }
        attempt = 0;
        await readBody(response.body);
        if (signal.aborted) return;
        throw new Error("SSE stream closed");
      } catch {
        if (signal.aborted) return;
        const delay = nextBackoffMs(attempt);
        attempt += 1;
        await wait(delay, signal);
      }
    }
  }

  void loop();
  return () => controller.abort();
}
