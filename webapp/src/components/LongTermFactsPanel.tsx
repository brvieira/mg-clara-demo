import { BrainCircuit, Sparkles } from "lucide-react";
import type { LongTermFact } from "@/types";

interface LongTermFactsPanelProps {
  facts: LongTermFact[];
  newFact: LongTermFact | null;
}

export function LongTermFactsPanel({ facts, newFact }: LongTermFactsPanelProps) {
  if (facts.length === 0 && !newFact) return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-white/5 p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--vz-dbg-text)]">
        <BrainCircuit className="size-3.5 text-[var(--vz-dbg-run)]" />
        Memória de longo prazo
      </div>

      {newFact && (
        <div className="mono flex items-start gap-1.5 rounded-md bg-[var(--vz-dbg-ok)]/10 p-2 text-[11px] text-[var(--vz-dbg-ok)]">
          <Sparkles className="mt-0.5 size-3 shrink-0" />
          <span>Novo fato salvo: {newFact.fact}</span>
        </div>
      )}

      {facts.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {facts.map((fact, i) => (
            <li key={i} className="mono text-[11px] text-[var(--vz-dbg-muted)]">
              · {fact.fact}
            </li>
          ))}
        </ul>
      ) : (
        <span className="text-[11px] text-[var(--vz-dbg-muted)]">Nenhum fato registrado ainda.</span>
      )}
    </div>
  );
}
