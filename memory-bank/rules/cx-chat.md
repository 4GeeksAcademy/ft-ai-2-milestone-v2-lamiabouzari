# First-line CX WebSocket

Chat uses the existing `first_line_cx` graph in `data/pipelines/support_agent.py`. The WebSocket changes the transport only.

- Session row: `chat_sessions` (`session_id`, `agent_id`, `user_id`, `client_id`, `status`, `created_at`). Messages live in `chat_messages` and survive reconnects. The LangGraph thread id is the session id.
- Endpoint: `WS /ws/chat/{session_id}?token=<jwt>`. JWT is the same secret as the backoffice and `GET /events/stream`. Missing or invalid tokens close with 4401 before any chat frame or agent run.
- One generation task per session publishes `token_chunk` on `chat.<session_id>`. Extra sockets subscribe; they do not start another run.
- `interrupt_requested` cancels that task. Tokens already produced stay on the assistant message with status `interrupted`. `new_input` starts a new assistant message. This is not LangGraph `interrupt()`.
- The account-support page at `uis/backoffice/src/app/knowledge/page.tsx` is the client. Reconnect waits 1s, 2s, 4s, … up to 30s and uses the same session id. `GET /events/stream` stays the RFP notification channel.
