import { useEffect } from 'react';
import { PanelLeftClose, RotateCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { CollapsedRail } from '@/components/CollapsedRail';
import { ClientCard } from '@/components/ClientCard';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { initials } from '@/lib/format';
import { useUIStore } from '@/store/uiStore';

export function ClientSidebar() {
  const leftMin = useUIStore((s) => s.leftMin);
  const toggleLeft = useUIStore((s) => s.toggleLeft);
  const clients = useUIStore((s) => s.clients);
  const clientsStatus = useUIStore((s) => s.clientsStatus);
  const selectedClientId = useUIStore((s) => s.selectedClientId);
  const selectClient = useUIStore((s) => s.selectClient);
  const loadClients = useUIStore((s) => s.loadClients);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  const activeClient = clients.find((c) => c.customer_id === selectedClientId);

  if (leftMin) {
    return (
      <CollapsedRail side="left" label="Clientes" onExpand={toggleLeft}>
        {activeClient && (
          <Avatar size="sm">
            <AvatarFallback className="bg-vz-roxo text-vz-branco">
              {initials(activeClient.name)}
            </AvatarFallback>
          </Avatar>
        )}
      </CollapsedRail>
    );
  }

  return (
    <aside className="flex h-full w-[288px] shrink-0 flex-col border-r border-[var(--vz-border)] bg-vz-branco-gelo">
      <div className="flex items-start justify-between gap-2 p-4 pb-2">
        <div>
          <h2 className="text-[11px] font-semibold tracking-[0.1em] text-[var(--vz-muted)] uppercase">
            Selecione o cliente
          </h2>
        </div>
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={toggleLeft}
                aria-label="Minimizar painel de clientes"
              />
            }
          >
            <PanelLeftClose className="size-4" />
          </TooltipTrigger>
          <TooltipContent side="right">Minimizar</TooltipContent>
        </Tooltip>
      </div>

      <ScrollArea className="min-h-0 flex-1 px-3">
        <div className="flex flex-col gap-2 pb-3">
          {clientsStatus === 'loading' &&
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-[76px] animate-pulse rounded-xl bg-vz-branco"
              />
            ))}

          {clientsStatus === 'error' && (
            <div className="flex flex-col items-start gap-2 rounded-xl border border-[var(--vz-border)] bg-vz-branco p-3 text-xs text-[var(--vz-muted)]">
              <span>Não foi possível carregar os clientes.</span>
              <Button variant="outline" size="sm" onClick={loadClients}>
                <RotateCw className="size-3.5" />
                Tentar de novo
              </Button>
            </div>
          )}

          {clientsStatus === 'success' &&
            clients.map((client) => (
              <ClientCard
                key={client.customer_id}
                client={client}
                selected={client.customer_id === selectedClientId}
                onSelect={() => selectClient(client.customer_id)}
              />
            ))}
        </div>
      </ScrollArea>

      <Separator />
      <div className="p-3 text-[11px] text-[var(--vz-faint)]">
        {clients.length} cliente(s) carregado(s)
      </div>
    </aside>
  );
}
