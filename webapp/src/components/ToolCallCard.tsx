import { FileSearch, MapPin, CalendarClock, CalendarPlus, CalendarX, CalendarCog, ListChecks, FilePlus, FileEdit, Wrench } from "lucide-react";
import { formatCodeBlock, toolLabel } from "@/lib/format";
import type { ToolCall } from "@/types";

const TOOL_ICONS: Record<string, typeof Wrench> = {
  vector_search_clausulas: FileSearch,
  buscar_oficinas_proximas: MapPin,
  consultar_agenda_pericia: CalendarClock,
  agendar_pericia: CalendarPlus,
  listar_agendamentos_cliente: ListChecks,
  cancelar_agendamento: CalendarX,
  alterar_agendamento: CalendarCog,
  listar_apolices_cliente: ListChecks,
  criar_apolice: FilePlus,
  atualizar_apolice: FileEdit,
};

function summarizeOutput(output: unknown): string {
  if (Array.isArray(output)) return `${output.length} resultado(s) encontrado(s)`;
  if (output && typeof output === "object" && "error" in (output as Record<string, unknown>)) {
    return `Erro: ${String((output as Record<string, unknown>).error)}`;
  }
  return formatCodeBlock(output, 3);
}

export function ToolCallCard({ call, receivedAt }: { call: ToolCall; receivedAt: string | null }) {
  const Icon = TOOL_ICONS[call.tool_name] ?? Wrench;

  return (
    <div className="relative pl-6">
      <span className="absolute top-1.5 left-0 size-2.5 rounded-full border-2 border-[var(--vz-dbg-bg)] bg-[var(--vz-dbg-ok)]" />
      <div className="rounded-lg bg-white/5 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon className="size-3.5 text-[var(--vz-dbg-ok)]" />
            <span className="mono text-xs text-[var(--vz-dbg-text)]">{toolLabel(call.tool_name)}</span>
          </div>
          <span className="rounded-full bg-[var(--vz-dbg-ok)]/15 px-2 py-0.5 text-[10px] font-medium text-[var(--vz-dbg-ok)]">
            concluído
          </span>
        </div>

        <pre className="mono mt-2 overflow-x-auto rounded-md bg-[var(--vz-dbg-code-bg)] p-2 text-[11px] leading-relaxed text-[var(--vz-dbg-code-val)]">
          {formatCodeBlock(call.input)}
        </pre>

        <div className="mono mt-2 text-[11px] text-[var(--vz-dbg-text)]">
          ↳ {summarizeOutput(call.output)}
        </div>

        {receivedAt && (
          <div className="mono mt-2 text-[10px] text-[var(--vz-dbg-muted)]">recebido às {receivedAt}</div>
        )}
      </div>
    </div>
  );
}
