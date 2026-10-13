# First-line CX WebSocket

Chat uses the existing `first_line_cx` graph in `data/pipelines/support_agent.py`. The WebSocket changes the transport only.

- Session row: `chat_sessions` (`session_id`, `agent_id`, `user_id`, `client_id`, `status`, `created_at`). Messages live in `chat_messages` and survive reconnects. The LangGraph thread id is the session id.
- Endpoint: `WS /ws/chat/{session_id}?token=<jwt>`. JWT is the same secret as the backoffice and `GET /events/stream`. Missing or invalid tokens close with 4401 before any chat frame or agent run.
- One generation task per session publishes `token_chunk` on `chat.<session_id>`. Extra sockets subscribe; they do not start another run.
- A model delta is published only after `guardrails.output_is_sensitive` allows it. Text that could still match that policy stays in server memory. A blocked turn is saved as the safe refusal with status `failed`, and `generation_completed` is not sent.
- `interrupt_requested` cancels that task. Tokens already produced stay on the assistant message with status `interrupted`. `new_input` starts a new assistant message. This is not LangGraph `interrupt()`.
- A generation that raises publishes `generation_failed` with a safe message and status `failed`. The client shows that message and can send the next turn. Token sequences restart at 1 for every turn.
- The account-support page at `uis/backoffice/src/app/knowledge/page.tsx` is the client. Six suggested questions sit above the message box and send through the same `user_message` path as Send. They stay disabled while the socket is not open or a reply is generating. Reconnect waits 1s, 2s, 4s, … up to 30s and uses the same session id. New conversation clears that stored id, calls `POST /chat/sessions`, and shows an empty transcript. Earlier `chat_messages` rows stay in Postgres. `GET /events/stream` stays the RFP notification channel.
- An expired or rejected JWT closes with 4401 and the page leaves the connecting status for sign-in. A missing or forbidden stored session (4403/4404) is dropped once so the next attempt creates a new session. The socket is accepted after the JWT check; the Postgres session lookup runs off the event loop so it does not hold the handshake.
