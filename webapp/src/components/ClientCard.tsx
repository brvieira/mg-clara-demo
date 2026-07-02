import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { initials } from "@/lib/format";
import type { ClientSummary } from "@/types";

const POLICY_TYPE_LABEL: Record<string, string> = {
  auto: "Auto",
  residencial: "Residencial",
};

interface ClientCardProps {
  client: ClientSummary;
  selected: boolean;
  onSelect: () => void;
}

export function ClientCard({ client, selected, onSelect }: ClientCardProps) {
  const uniqueTypes = [...new Set(client.policies.map((p) => p.type))];
  const firstPolicy = client.policies[0];
  const extraCount = client.policies.length - 1;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`relative flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-all duration-150 ${
        selected
          ? "border-[1.5px] border-[var(--vz-accent)] bg-vz-branco shadow-[0_1px_3px_rgba(13,27,42,.06)]"
          : "border-transparent bg-vz-branco-gelo hover:bg-vz-branco"
      }`}
    >
      <Avatar>
        <AvatarFallback
          className={selected ? "bg-vz-roxo text-vz-branco" : "bg-[var(--vz-faint)]/20 text-[var(--vz-muted)]"}
        >
          {initials(client.name)}
        </AvatarFallback>
      </Avatar>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="truncate text-sm font-semibold text-vz-ink">{client.name}</span>
        {firstPolicy && (
          <span className="mono truncate text-xs text-[var(--vz-muted)]">
            {firstPolicy.policy_id}
            {extraCount > 0 && ` +${extraCount}`}
          </span>
        )}
        <div className="flex flex-wrap gap-1 pt-0.5">
          {uniqueTypes.map((type) => (
            <Badge key={type} variant="default" className="bg-vz-roxo text-vz-branco">
              {POLICY_TYPE_LABEL[type] ?? type}
            </Badge>
          ))}
          {client.open_claims_count > 0 && (
            <Badge variant="outline">{client.open_claims_count} sinistro(s) em aberto</Badge>
          )}
        </div>
      </div>

      {selected && (
        <span className="absolute top-3 right-3 size-1.5 rounded-full bg-[var(--vz-accent)]" />
      )}
    </button>
  );
}
