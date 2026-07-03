import { useEffect, useRef, useState } from "react";
import { Send, RotateCw } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatBubble } from "@/components/ChatBubble";
import { initials, contactLabel } from "@/lib/format";
import { useUIStore } from "@/store/uiStore";

export function ChatPanel() {
  const clients = useUIStore((s) => s.clients);
  const selectedClientId = useUIStore((s) => s.selectedClientId);
  const conversations = useUIStore((s) => s.conversations);
  const sendMessage = useUIStore((s) => s.sendMessage);
  const openModal = useUIStore((s) => s.openModal);
  const startNewSession = useUIStore((s) => s.startNewSession);

  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const client = clients.find((c) => c.customer_id === selectedClientId);
  const conversation = selectedClientId ? conversations[selectedClientId] : undefined;
  const messages = conversation?.messages ?? [];
  const isSending = messages.some((m) => m.pending);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.text]);

  if (!client || !selectedClientId) {
    return (
      <main className="flex flex-1 items-center justify-center bg-vz-branco-gelo text-sm text-[var(--vz-muted)]">
        Selecione um cliente para iniciar o atendimento.
      </main>
    );
  }

  const handleSend = () => {
    const text = draft.trim();
    if (!text || isSending) return;
    setDraft("");
    sendMessage(selectedClientId, text);
  };

  const handleNewSession = () => {
    if (isSending) return;
    startNewSession(selectedClientId);
  };

  return (
    <main className="flex min-h-0 flex-1 flex-col bg-vz-branco-gelo">
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--vz-border)] bg-vz-branco px-5 py-3">
        <div className="flex items-center gap-3">
          <Avatar>
            <AvatarFallback className="bg-vz-roxo text-vz-branco">
              {initials(client.name)}
            </AvatarFallback>
          </Avatar>
          <div>
            <div className="text-sm font-semibold text-vz-ink">{client.name}</div>
            <div className="text-xs text-[var(--vz-muted)]">
              {client.policies.length} apólice(s) ativa(s)
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-[var(--vz-border)] px-2.5 py-1 text-xs text-[var(--vz-muted)]">
            {contactLabel(client.contact_preference)}
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={handleNewSession}
            disabled={isSending}
            aria-label="Iniciar nova sessão"
          >
            <RotateCw className="size-3.5" />
            Nova sessão
          </Button>
          <Button size="sm" onClick={openModal} className="bg-vz-roxo text-vz-branco hover:bg-vz-roxo/90">
            Ver perfil completo
          </Button>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div ref={scrollRef} className="flex flex-col gap-3 p-5">
          {messages.length === 0 && (
            <span className="mx-auto rounded-full bg-vz-branco px-3 py-1 text-[11px] text-[var(--vz-faint)]">
              Hoje
            </span>
          )}
          {messages.map((message) => (
            <ChatBubble key={message.id} message={message} />
          ))}
        </div>
      </ScrollArea>

      <div className="flex shrink-0 items-center gap-2 border-t border-[var(--vz-border)] bg-vz-branco p-3">
        <Input
          value={draft}
          disabled={isSending}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Digite uma mensagem para o agente…"
          className="flex-1"
        />
        <Button
          size="icon"
          onClick={handleSend}
          disabled={isSending || !draft.trim()}
          aria-label="Enviar mensagem"
          className="bg-vz-roxo text-vz-branco hover:bg-vz-roxo/90"
        >
          <Send className="size-4" />
        </Button>
      </div>
    </main>
  );
}
