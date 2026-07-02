import { PanelRightClose } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CollapsedRail } from "@/components/CollapsedRail";
import { ToolCallCard } from "@/components/ToolCallCard";
import { LongTermFactsPanel } from "@/components/LongTermFactsPanel";
import { useUIStore } from "@/store/uiStore";

export function DebugPanel() {
  const rightMin = useUIStore((s) => s.rightMin);
  const toggleRight = useUIStore((s) => s.toggleRight);
  const selectedClientId = useUIStore((s) => s.selectedClientId);
  const conversations = useUIStore((s) => s.conversations);

  const conversation = selectedClientId ? conversations[selectedClientId] : undefined;
  const lastDebug = conversation?.lastDebug ?? null;
  const toolCalls = lastDebug?.tool_calls_made ?? [];
  const toolCount = conversation?.toolCallHistory.length ?? 0;
  const sessionId = conversation?.thread_id ?? "—";

  if (rightMin) {
    return <CollapsedRail side="right" label="Debug · Ações" onExpand={toggleRight} accentDot dark />;
  }

  return (
    <aside className="flex h-full w-[392px] shrink-0 flex-col bg-[var(--vz-dbg-bg)] text-[var(--vz-dbg-text)]">
      <div className="flex shrink-0 items-center justify-between p-3 pb-2">
        <Tabs defaultValue="actions" className="flex-1">
          <div className="flex items-center justify-between">
            <TabsList className="bg-white/10">
              <TabsTrigger value="actions" className="text-[var(--vz-dbg-text)] data-active:text-[var(--vz-dbg-bg)]">
                Ações do agente
              </TabsTrigger>
              <TabsTrigger value="raw" className="text-[var(--vz-dbg-text)] data-active:text-[var(--vz-dbg-bg)]">
                Logs brutos
              </TabsTrigger>
            </TabsList>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={toggleRight}
                    aria-label="Minimizar painel de debug"
                    className="text-[var(--vz-dbg-text)] hover:bg-white/10"
                  />
                }
              >
                <PanelRightClose className="size-4" />
              </TooltipTrigger>
              <TooltipContent side="left">Minimizar</TooltipContent>
            </Tooltip>
          </div>

          <div className="mono mt-3 grid grid-cols-2 gap-2 text-[11px]">
            <div className="rounded-lg bg-white/5 p-2">
              <div className="text-[var(--vz-dbg-muted)]">Sessão</div>
              <div className="truncate text-[var(--vz-dbg-text)]">{sessionId}</div>
            </div>
            <div className="rounded-lg bg-white/5 p-2">
              <div className="text-[var(--vz-dbg-muted)]">Ferramentas</div>
              <div className="text-[var(--vz-dbg-ok)]">{toolCount}</div>
            </div>
          </div>

          <TabsContent value="actions" className="mt-3">
            <ScrollArea className="h-[calc(100vh-260px)]">
              <div className="flex flex-col gap-3 pr-2">
                <LongTermFactsPanel
                  facts={lastDebug?.long_term_facts ?? []}
                  newFact={lastDebug?.new_fact_saved ?? null}
                />
                {toolCalls.length === 0 ? (
                  <span className="text-[11px] text-[var(--vz-dbg-muted)]">
                    Nenhuma ferramenta acionada ainda nesta conversa.
                  </span>
                ) : (
                  toolCalls.map((call, i) => (
                    <ToolCallCard key={i} call={call} receivedAt={conversation?.lastDebugAt ?? null} />
                  ))
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="raw" className="mt-3">
            <ScrollArea className="h-[calc(100vh-260px)]">
              <pre className="mono overflow-x-auto rounded-lg bg-[var(--vz-dbg-code-bg)] p-3 text-[11px] leading-relaxed text-[var(--vz-dbg-code-val)]">
                {lastDebug ? JSON.stringify(lastDebug, null, 2) : "Nenhum turno ainda."}
              </pre>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>
    </aside>
  );
}
