import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { bemLabel, contactLabel, initials } from "@/lib/format";
import { useUIStore } from "@/store/uiStore";
import type { Claim, Policy } from "@/types";

const POLICY_TYPE_LABEL: Record<string, string> = { auto: "Auto", residencial: "Residencial" };

function PolicyStatusBadge({ status }: { status: Policy["status"] }) {
  return status === "active" ? (
    <Badge className="bg-[var(--vz-success)]/15 text-[var(--vz-success-ink)]">Ativa</Badge>
  ) : (
    <Badge className="bg-amber-100 text-amber-800">Pendente</Badge>
  );
}

function ClaimStatusBadge({ status }: { status: string }) {
  if (status === "em_analise") return <Badge className="bg-amber-100 text-amber-800">Em análise</Badge>;
  if (status === "aprovado" || status === "pago")
    return <Badge className="bg-[var(--vz-success)]/15 text-[var(--vz-success-ink)]">{status === "pago" ? "Pago" : "Aprovado"}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

export function ClientProfileDialog() {
  const modalOpen = useUIStore((s) => s.modalOpen);
  const closeModal = useUIStore((s) => s.closeModal);
  const selectedClientId = useUIStore((s) => s.selectedClientId);
  const clientProfile = useUIStore((s) => s.clientProfile);
  const sendMessage = useUIStore((s) => s.sendMessage);

  const profile = selectedClientId ? clientProfile[selectedClientId] : undefined;

  const handleConsultClauses = (policyId: string) => {
    if (!selectedClientId) return;
    closeModal();
    sendMessage(selectedClientId, `Quais são as coberturas da minha apólice ${policyId}?`);
  };

  return (
    <Dialog open={modalOpen} onOpenChange={(open) => !open && closeModal()}>
      <DialogContent className="max-w-lg gap-0 p-0 sm:max-w-lg">
        {!profile ? (
          <div className="p-6 text-sm text-[var(--vz-muted)]">Carregando perfil…</div>
        ) : (
          <>
            <DialogHeader className="gap-3 bg-vz-roxo p-5 text-vz-branco">
              <div className="flex items-center gap-3">
                <Avatar size="lg">
                  <AvatarFallback className="bg-white/15 text-vz-branco">
                    {initials(profile.name)}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <DialogTitle className="text-vz-branco">{profile.name}</DialogTitle>
                  <div className="mono text-xs text-white/70">{profile.customer_id}</div>
                </div>
              </div>
            </DialogHeader>

            <ScrollArea className="max-h-[70vh]">
              <div className="flex flex-col gap-5 p-5">
                <section className="flex flex-col gap-1.5">
                  <h3 className="text-[11px] font-semibold tracking-wide text-[var(--vz-muted)] uppercase">
                    Dados de contato
                  </h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <div className="text-xs text-[var(--vz-faint)]">CEP</div>
                      <div className="mono">{profile.cep}</div>
                    </div>
                    <div>
                      <div className="text-xs text-[var(--vz-faint)]">Canal preferido</div>
                      <div>{contactLabel(profile.contact_preference)}</div>
                    </div>
                  </div>
                </section>

                <Separator />

                <section className="flex flex-col gap-2">
                  <h3 className="text-[11px] font-semibold tracking-wide text-[var(--vz-muted)] uppercase">
                    Apólices
                  </h3>
                  {profile.policies.map((policy) => (
                    <div key={policy.policy_id} className="rounded-lg border border-[var(--vz-border)] p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="mono text-sm font-medium">{policy.policy_id}</span>
                        <div className="flex gap-1.5">
                          <Badge className="bg-vz-roxo text-vz-branco">
                            {POLICY_TYPE_LABEL[policy.type] ?? policy.type}
                          </Badge>
                          <PolicyStatusBadge status={policy.status} />
                        </div>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-[var(--vz-muted)]">
                        <div>
                          <div className="text-[var(--vz-faint)]">Renovação</div>
                          <div>{policy.renewal_date}</div>
                        </div>
                        <div>
                          <div className="text-[var(--vz-faint)]">{bemLabel(policy)}</div>
                          <div>{policy.vehicle ?? policy.address}</div>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2 w-full"
                        onClick={() => handleConsultClauses(policy.policy_id)}
                      >
                        Consultar cláusulas da apólice
                      </Button>
                    </div>
                  ))}
                </section>

                <Separator />

                <section className="flex flex-col gap-2">
                  <h3 className="text-[11px] font-semibold tracking-wide text-[var(--vz-muted)] uppercase">
                    Sinistros
                  </h3>
                  {profile.claims.length === 0 ? (
                    <span className="text-sm text-[var(--vz-faint)]">Nenhum sinistro registrado.</span>
                  ) : (
                    profile.claims.map((claim: Claim) => (
                      <div key={claim.claim_id} className="rounded-lg border border-[var(--vz-border)] p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="mono text-sm font-medium">{claim.claim_id}</span>
                          <ClaimStatusBadge status={claim.status} />
                        </div>
                        <div className="mt-1 text-xs text-[var(--vz-muted)]">
                          {claim.type} · aberto em {claim.opened_at}
                        </div>
                        <p className="mt-1.5 text-sm">{claim.description}</p>
                      </div>
                    ))
                  )}
                </section>
              </div>
            </ScrollArea>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
