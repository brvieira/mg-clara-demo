import type { ClientSummary, CustomerProfile, TurnDebug } from "@/types";

const AGENT_BASE_URL = import.meta.env.VITE_API_BASE_URL as string;
const CUSTOMER_API_BASE_URL = import.meta.env.VITE_CUSTOMER_API_BASE_URL as string;

export async function getHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${AGENT_BASE_URL}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function getClients(): Promise<ClientSummary[]> {
  const res = await fetch(`${CUSTOMER_API_BASE_URL}/clients`);
  if (!res.ok) throw new Error(`GET /clients falhou (${res.status})`);
  return res.json();
}

export async function getClientProfile(customerId: string): Promise<CustomerProfile> {
  const res = await fetch(`${CUSTOMER_API_BASE_URL}/clients/${customerId}`);
  if (!res.ok) throw new Error(`GET /clients/${customerId} falhou (${res.status})`);
  return res.json();
}

// Fallback não-streaming (seção 5.2 da spec) — não usado pelo ChatPanel, que
// sempre fala com /chat/stream; mantido aqui só por paridade com o contrato da API.
export async function postChat(
  customerId: string,
  message: string,
  threadId: string | null
): Promise<{ thread_id: string; response: string; debug: TurnDebug }> {
  const res = await fetch(`${AGENT_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_id: customerId, message, thread_id: threadId }),
  });
  if (!res.ok) throw new Error(`POST /chat falhou (${res.status})`);
  return res.json();
}

export { AGENT_BASE_URL };
