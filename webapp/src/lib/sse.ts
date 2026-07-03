import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { ChatStreamEvent } from "@/types";
import { AGENT_BASE_URL } from "@/lib/api";

interface StreamChatArgs {
  customerId: string;
  message: string;
  threadId: string | null;
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
}

// Parser de POST /chat/stream (ai-agent) — EventSource nativo do browser não
// suporta POST/corpo, por isso @microsoft/fetch-event-source (spec seção 2).
export async function streamChat({
  customerId,
  message,
  threadId,
  onEvent,
  signal,
}: StreamChatArgs): Promise<void> {
  await fetchEventSource(`${AGENT_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_id: customerId, message, thread_id: threadId }),
    signal,
    async onopen(res) {
      if (!res.ok) {
        throw new Error(`POST /chat/stream falhou (${res.status})`);
      }
    },
    onmessage(msg) {
      if (!msg.data) return;
      onEvent(JSON.parse(msg.data) as ChatStreamEvent);
    },
    onerror(err) {
      // Relança para interromper o retry automático da lib — o chamador trata
      // o erro via try/catch e emite seu próprio evento de UI (bolha de sistema).
      throw err;
    },
  });
}
