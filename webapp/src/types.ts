export type PolicyType = "auto" | "residencial";
export type PolicyStatus = "active" | "pending";
export type Role = "user" | "agent" | "system";
export type ContactPreference = "whatsapp" | "email" | "telefone";

export interface Policy {
  policy_id: string;
  type: PolicyType;
  status: PolicyStatus;
  renewal_date: string;
  vehicle?: string;
  address?: string;
}

export interface Claim {
  claim_id: string;
  type: string;
  status: string;
  opened_at: string;
  description: string;
}

export interface CustomerProfile {
  customer_id: string;
  name: string;
  cep: string;
  policies: Policy[];
  claims: Claim[];
  contact_preference: ContactPreference;
}

// GET /clients (customer-api) — versão resumida para a sidebar
export interface ClientSummary {
  customer_id: string;
  name: string;
  policies: { policy_id: string; type: PolicyType }[];
  open_claims_count: number;
  contact_preference: ContactPreference;
}

export interface ChatMessage {
  id: string;
  role: Role;
  text: string;
  time: string;
  pending?: boolean;
}

// Uma entrada real de debug.tool_calls_made (ai-agent)
export interface ToolCall {
  tool_name: string;
  input: Record<string, unknown>;
  output: unknown;
}

export interface LongTermFact {
  fact: string;
  recorded_at: string;
}

export interface TurnDebug {
  long_term_facts: LongTermFact[];
  new_fact_saved: LongTermFact | null;
  tool_calls_made: ToolCall[];
}

// Estado de conversa por cliente, mantido só no frontend (não persiste entre reloads)
export interface ClientConversation {
  thread_id: string | null;
  messages: ChatMessage[];
  lastDebug: TurnDebug | null;
  // Timestamp de chegada do evento `done` mais recente — não vem da API; é só
  // uma aproximação client-side do "momento" da chamada (spec v2, seção 6.4).
  lastDebugAt: string | null;
  toolCallHistory: ToolCall[];
}

export type HealthStatus = "checking" | "online" | "offline";

// Eventos do POST /chat/stream (ai-agent, SSE)
export type ChatStreamEvent =
  | { type: "start"; thread_id: string }
  | { type: "token"; content: string }
  | { type: "done"; response: string; debug: TurnDebug }
  | { type: "error"; detail: string };
