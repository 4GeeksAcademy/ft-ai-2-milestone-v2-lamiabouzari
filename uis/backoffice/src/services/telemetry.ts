"use client";

type TelemetryProperties = Record<string, unknown>;

interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string;
  event_type: string;
  schemaVersion: string;
  requestId: string | null;
  properties: TelemetryProperties;
}

const STORAGE_SESSION_KEY = "trackflow.telemetry.session_id";
const STORAGE_USER_KEY = "trackflow.telemetry.anonymous_user_id";
const SCHEMA_VERSION = "1.0.0";
const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_THRESHOLD = 20;
const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 500;

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

class TelemetryService {
  private queue: TelemetryEvent[] = [];

  private flushTimer: number | null = null;

  private isFlushing = false;

  private get endpoint(): string | undefined {
    return process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
  }

  private getSessionId(): string {
    return this.getStoredId(STORAGE_SESSION_KEY);
  }

  private getUserId(): string {
    return this.getStoredId(STORAGE_USER_KEY);
  }

  private getStoredId(key: string): string {
    if (typeof window === "undefined") {
      return createId();
    }

    const existing = window.sessionStorage.getItem(key);
    if (existing) {
      return existing;
    }

    const generated = createId();
    window.sessionStorage.setItem(key, generated);
    return generated;
  }

  private createEvent(
    eventType: string,
    properties: TelemetryProperties,
  ): TelemetryEvent {
    return {
      eventId: createId(),
      timestamp: new Date().toISOString(),
      sessionId: this.getSessionId(),
      userId: this.getUserId(),
      event_type: eventType,
      schemaVersion: SCHEMA_VERSION,
      requestId: null,
      properties,
    };
  }

  private async send(events: TelemetryEvent[]): Promise<boolean> {
    if (!this.endpoint) {
      return false;
    }

    for (let retry = 0; retry <= MAX_RETRIES; retry += 1) {
      try {
        const response = await fetch(this.endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ events }),
          keepalive: true,
        });

        if (response.ok) {
          return true;
        }
      } catch {
        // Retry transient failures without affecting the calling UI.
      }

      if (retry < MAX_RETRIES) {
        await new Promise((resolve) => {
          window.setTimeout(resolve, RETRY_BASE_DELAY_MS * 2 ** retry);
        });
      }
    }

    return false;
  }

  private sendWithBeacon(events: TelemetryEvent[]): boolean {
    if (!this.endpoint || typeof navigator.sendBeacon !== "function") {
      return false;
    }

    const body = new Blob([JSON.stringify({ events })], {
      type: "application/json",
    });
    return navigator.sendBeacon(this.endpoint, body);
  }

  private async flush(): Promise<void> {
    if (this.isFlushing || this.queue.length === 0 || !this.endpoint) {
      return;
    }

    this.isFlushing = true;
    const events = this.queue.splice(0, this.queue.length);
    const sent = await this.send(events);
    if (!sent) {
      // Failed events are intentionally discarded after their final retry.
    }
    this.isFlushing = false;
  }

  private handleVisibilityChange = (): void => {
    if (document.visibilityState !== "hidden" || this.queue.length === 0) {
      return;
    }

    const events = this.queue.splice(0, this.queue.length);
    if (!this.sendWithBeacon(events)) {
      this.queue.unshift(...events);
      void this.flush();
    }
  };

  /** Add one allowlisted event to the in-memory queue. */
  track(eventType: string, properties: TelemetryProperties): void {
    if (typeof window === "undefined") {
      return;
    }

    this.queue.push(this.createEvent(eventType, properties));
    if (this.queue.length >= FLUSH_THRESHOLD) {
      void this.flush();
    }
  }

  start(): void {
    if (this.flushTimer || typeof window === "undefined") {
      return;
    }

    this.flushTimer = window.setInterval(() => {
      void this.flush();
    }, FLUSH_INTERVAL_MS);
    document.addEventListener("visibilitychange", this.handleVisibilityChange);
  }

  stop(): void {
    if (this.flushTimer) {
      window.clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    document.removeEventListener("visibilitychange", this.handleVisibilityChange);
  }
}

export const telemetryService = new TelemetryService();