import { useEffect } from 'react';
import logotipo from '@/assets/logo.svg';
import { useUIStore } from '@/store/uiStore';

const HEALTH_LABEL: Record<string, string> = {
  checking: 'Verificando…',
  online: 'Agente online',
  offline: 'Agente indisponível',
};

const HEALTH_DOT: Record<string, string> = {
  checking: 'bg-[var(--vz-faint)]',
  online: 'bg-[var(--vz-success)]',
  offline: 'bg-red-500',
};

export function AppHeader() {
  const health = useUIStore((s) => s.health);
  const startHealthPolling = useUIStore((s) => s.startHealthPolling);

  useEffect(() => startHealthPolling(), [startHealthPolling]);

  return (
    <header className="flex h-[60px] shrink-0 items-center justify-between border-b border-[var(--vz-border)] bg-vz-branco px-5">
      <div className="flex items-center gap-3">
        <img
          src={logotipo}
          alt="Vivaz Seguros"
          className="h-[30px] w-auto object-contain"
        />
        <span className="hidden text-xs font-light text-[var(--vz-muted)] sm:inline">
          Clara - Assistente virtual da Vivaz Seguros
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-full border border-[var(--vz-border)] px-2.5 py-1 text-xs font-medium">
          <span className={`size-2 rounded-full ${HEALTH_DOT[health]}`} />
          {HEALTH_LABEL[health]}
        </span>
        <span className="mono rounded-full bg-[var(--vz-branco-gelo)] px-2.5 py-1 text-[11px] text-[var(--vz-muted)]">
          gpt-4.1-mini
        </span>
        <span className="mono rounded-full bg-[var(--vz-branco-gelo)] px-2.5 py-1 text-[11px] text-[var(--vz-muted)]">
          text-embedding-3-small
        </span>
      </div>
    </header>
  );
}
