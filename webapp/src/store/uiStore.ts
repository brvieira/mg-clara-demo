import { create } from "zustand";
import { getClientProfile, getClients, getHealth } from "@/lib/api";
import { streamChat } from "@/lib/sse";
import { formatTime } from "@/lib/format";
import type {
  ChatMessage,
  ClientConversation,
  ClientSummary,
  CustomerProfile,
  HealthStatus,
} from "@/types";

type ClientsStatus = "idle" | "loading" | "error" | "success";

function emptyConversation(): ClientConversation {
  return {
    thread_id: null,
    messages: [],
    lastDebug: null,
    lastDebugAt: null,
    toolCallHistory: [],
  };
}

interface UIState {
  selectedClientId: string | null;
  modalOpen: boolean;
  leftMin: boolean;
  rightMin: boolean;

  clients: ClientSummary[];
  clientsStatus: ClientsStatus;
  clientProfile: Record<string, CustomerProfile>;
  health: HealthStatus;

  conversations: Record<string, ClientConversation>;

  loadClients: () => Promise<void>;
  selectClient: (customerId: string) => void;
  toggleLeft: () => void;
  toggleRight: () => void;
  openModal: () => Promise<void>;
  closeModal: () => void;
  sendMessage: (customerId: string, text: string) => Promise<void>;
  startNewSession: (customerId: string) => void;
  startHealthPolling: () => () => void;
}

function withConversation(
  conversations: Record<string, ClientConversation>,
  customerId: string,
  update: (conv: ClientConversation) => ClientConversation
): Record<string, ClientConversation> {
  const current = conversations[customerId] ?? emptyConversation();
  return { ...conversations, [customerId]: update(current) };
}

export const useUIStore = create<UIState>((set, get) => ({
  selectedClientId: null,
  modalOpen: false,
  leftMin: false,
  rightMin: false,

  clients: [],
  clientsStatus: "idle",
  clientProfile: {},
  health: "checking",

  conversations: {},

  loadClients: async () => {
    set({ clientsStatus: "loading" });
    try {
      const clients = await getClients();
      set((state) => ({
        clients,
        clientsStatus: "success",
        selectedClientId: state.selectedClientId ?? clients[0]?.customer_id ?? null,
      }));
    } catch {
      set({ clientsStatus: "error" });
    }
  },

  selectClient: (customerId) => {
    set((state) => ({
      selectedClientId: customerId,
      conversations:
        customerId in state.conversations
          ? state.conversations
          : { ...state.conversations, [customerId]: emptyConversation() },
    }));
  },

  toggleLeft: () => set((state) => ({ leftMin: !state.leftMin })),
  toggleRight: () => set((state) => ({ rightMin: !state.rightMin })),

  openModal: async () => {
    const customerId = get().selectedClientId;
    if (!customerId) return;
    set({ modalOpen: true });
    try {
      // Sempre busca de novo ao abrir (seção 6.5) — o cache só evita uma tela
      // vazia enquanto essa chamada está em andamento (stale-while-revalidate).
      const profile = await getClientProfile(customerId);
      set((state) => ({ clientProfile: { ...state.clientProfile, [customerId]: profile } }));
    } catch {
      // Mantém o que já estiver em cache (se houver); dialog trata ausência como erro.
    }
  },

  closeModal: () => set({ modalOpen: false }),

  sendMessage: async (customerId, text) => {
    const conv = get().conversations[customerId] ?? emptyConversation();
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text,
      time: formatTime(),
    };
    const agentMessageId = crypto.randomUUID();
    const agentMessage: ChatMessage = {
      id: agentMessageId,
      role: "agent",
      text: "",
      time: formatTime(),
      pending: true,
    };

    set((state) => ({
      conversations: withConversation(state.conversations, customerId, (c) => ({
        ...c,
        messages: [...c.messages, userMessage, agentMessage],
      })),
    }));

    const failWithSystemMessage = (detail: string) => {
      set((state) => ({
        conversations: withConversation(state.conversations, customerId, (c) => ({
          ...c,
          messages: c.messages
            .filter((m) => m.id !== agentMessageId)
            .concat({ id: crypto.randomUUID(), role: "system", text: detail, time: formatTime() }),
        })),
      }));
    };

    try {
      await streamChat({
        customerId,
        message: text,
        threadId: conv.thread_id,
        onEvent: (event) => {
          set((state) => ({
            conversations: withConversation(state.conversations, customerId, (c) => {
              switch (event.type) {
                case "start":
                  return { ...c, thread_id: event.thread_id };
                case "token":
                  return {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === agentMessageId ? { ...m, text: m.text + event.content } : m
                    ),
                  };
                case "done":
                  return {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === agentMessageId
                        ? { ...m, text: event.response, pending: false }
                        : m
                    ),
                    lastDebug: event.debug,
                    lastDebugAt: formatTime(),
                    toolCallHistory: [...c.toolCallHistory, ...event.debug.tool_calls_made],
                  };
                case "error":
                  return c; // tratado no catch/failWithSystemMessage abaixo
                default:
                  return c;
              }
            }),
          }));
          if (event.type === "error") failWithSystemMessage(event.detail);
        },
      });
    } catch (err) {
      failWithSystemMessage(err instanceof Error ? err.message : "Erro de conexão com o agente.");
    }
  },

  startNewSession: (customerId) => {
    set((state) => ({
      conversations: { ...state.conversations, [customerId]: emptyConversation() },
    }));
  },

  startHealthPolling: () => {
    const check = async () => set({ health: (await getHealth()) ? "online" : "offline" });
    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  },
}));
