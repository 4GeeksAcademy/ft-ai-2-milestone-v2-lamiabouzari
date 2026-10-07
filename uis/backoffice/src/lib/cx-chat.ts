import { getToken } from "@/lib/auth";

export interface ChatMessageView {
  message_id: string;
  role: "user" | "assistant";
  text: string;
  status: string;
  sequence?: number;
}

export interface SessionSnapshot {
  session_id: string;
  agent_id: string;
  user_id: string;
  client_id: string;
  status: string;
  created_at: string;
  thread_id: string;
  messages: ChatMessageView[];
}

export interface TokenChunk {
  session_id: string;
  token: string;
  sequence: number;
}

export interface GenerationInterrupted {
  session_id: string;
  message_id: string;
  status: string;
}

export interface GenerationCompleted {
  session_id: string;
  message_id: string;
}

export interface UserMessageEvent {
  session_id: string;
  message_id: string;
  text: string;
}

export type ConnectionState = "open" | "reconnecting" | "closed";

interface ChatHandlers {
  onSnapshot: (snapshot: SessionSnapshot) => void;
  onUserMessage: (message: UserMessageEvent) => void;
  onToken: (chunk: TokenChunk) => void;
  onInterrupted: (event: GenerationInterrupted) => void;
  onCompleted: (event: GenerationCompleted) => void;
  onConnectionChange?: (state: ConnectionState) => void;
}

export function nextBackoffMs(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, 30_000);
}

export function appliedSnapshotSequence(messages: ChatMessageView[]): number {
  let highest = 0;
  for (const message of messages) {
    if (message.role === "assistant" && message.status === "generating" && typeof message.sequence === "number") {
      highest = Math.max(highest, message.sequence);
    }
  }
  return highest;
}

export function acceptTokenSequence(applied: number, sequence: number): boolean {
  return sequence > applied;
}

export function chatWebSocketUrl(sessionId: string, token: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL || "/api/backend";
  const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const url = new URL(base, origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  const prefix = url.pathname.replace(/\/$/, "");
  url.pathname = `${prefix}/ws/chat/${sessionId}`;
  url.search = "";
  url.searchParams.set("token", token);
  url.searchParams.set("thread_id", sessionId);
  return url.toString();
}

export function startCxChat(sessionId: string, token: string, handlers: ChatHandlers): {
  stop: () => void;
  send: (event: string, data: Record<string, string>) => void;
} {
  let stopped = false;
  let attempt = 0;
  let socket: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const connect = () => {
    if (stopped) return;
    const previous = socket;
    if (previous && previous.readyState !== WebSocket.CLOSED) {
      socket = null;
      previous.close();
    }
    const current = new WebSocket(chatWebSocketUrl(sessionId, token));
    socket = current;
    current.onopen = () => {
      attempt = 0;
      handlers.onConnectionChange?.("open");
    };
    current.onmessage = (message) => {
      let payload: { event?: string; data?: unknown };
      try {
        payload = JSON.parse(String(message.data)) as { event?: string; data?: unknown };
      } catch {
        return;
      }
      const data = payload.data;
      if (payload.event === "session_snapshot") {
        handlers.onSnapshot(data as SessionSnapshot);
      } else if (payload.event === "user_message") {
        handlers.onUserMessage(data as UserMessageEvent);
      } else if (payload.event === "token_chunk") {
        handlers.onToken(data as TokenChunk);
      } else if (payload.event === "generation_interrupted") {
        handlers.onInterrupted(data as GenerationInterrupted);
      } else if (payload.event === "generation_completed") {
        handlers.onCompleted(data as GenerationCompleted);
      }
    };
    current.onclose = (event) => {
      if (stopped || socket !== current) return;
      if (event.code === 4401 || event.code === 4403 || event.code === 4404) {
        handlers.onConnectionChange?.("closed");
        return;
      }
      handlers.onConnectionChange?.("reconnecting");
      const delay = nextBackoffMs(attempt);
      attempt += 1;
      timer = setTimeout(connect, delay);
    };
  };

  connect();

  return {
    stop() {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    },
    send(event, data) {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(JSON.stringify({ event, data }));
    },
  };
}

export function readStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("trackflow_cx_session_id");
}

export function storeSessionId(sessionId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem("trackflow_cx_session_id", sessionId);
}

export function currentAccessToken(): string | null {
  return getToken();
}
