import type { ContactPreference, Policy } from "@/types";

// Tabela tool_name → label amigável (seção 6.4 da spec v2). Tool não mapeada:
// usar o nome cru como label (fallback abaixo).
const TOOL_LABELS: Record<string, string> = {
  vector_search_clausulas: "Busca de cláusulas",
  buscar_oficinas_proximas: "Busca de oficinas parceiras",
  consultar_agenda_pericia: "Consulta de agenda de perícia",
  agendar_pericia: "Agendamento de perícia",
  listar_agendamentos_cliente: "Consulta de agendamentos",
  cancelar_agendamento: "Cancelamento de agendamento",
  alterar_agendamento: "Alteração de agendamento",
  listar_apolices_cliente: "Consulta de apólices",
  criar_apolice: "Criação de apólice",
  atualizar_apolice: "Atualização de apólice",
};

export function toolLabel(toolName: string): string {
  return TOOL_LABELS[toolName] ?? toolName;
}

const CONTACT_LABELS: Record<ContactPreference, string> = {
  whatsapp: "WhatsApp",
  email: "E-mail",
  telefone: "Telefone",
};

export function contactLabel(pref: ContactPreference): string {
  return CONTACT_LABELS[pref] ?? pref;
}

export function bemLabel(policy: Pick<Policy, "type">): string {
  return policy.type === "auto" ? "Veículo segurado" : "Imóvel segurado";
}

const CHIP_PATTERNS = [/\bSIN-\d{4}-\d{2}\b/g, /\bPOL-(AUTO|RES)-\d{4}\b/g, /\bEND-\d{4}\b/g];

// Nice-to-have (seção 6.3): destaques extraídos por regex do texto da resposta,
// já que a API não retorna mais um campo `chips` estruturado.
export function extractChips(text: string): string[] {
  const found = new Set<string>();
  for (const pattern of CHIP_PATTERNS) {
    for (const match of text.matchAll(pattern)) {
      found.add(match[0]);
    }
  }
  return [...found];
}

export function formatTime(date: Date = new Date()): string {
  return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

// Serializa um valor arbitrário (input/output de tool call) como bloco de
// código, truncado a um número razoável de linhas (seção 6.4).
export function formatCodeBlock(value: unknown, maxLines = 6): string {
  const json = JSON.stringify(value, null, 2) ?? "null";
  const lines = json.split("\n");
  if (lines.length <= maxLines) return json;
  return [...lines.slice(0, maxLines), "…"].join("\n");
}
