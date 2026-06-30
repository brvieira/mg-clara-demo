"""
Servidor MCP standalone que simula o sistema de oficinas e peritos parceiros da ClaraSeg.

Transporte: stdio — o processo é iniciado como subprocesso pelo agente.
Executar diretamente para testar: python mcp_servers/workshop_server.py
"""
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
import random

mcp = FastMCP("oficinas-parceiras")

OFICINAS_MOCK = [
    {
        "id": "of_001",
        "nome": "Auto Center Vivaz Zona Sul",
        "servicos": ["colisao", "pintura", "mecanica"],
    },
    {
        "id": "of_002",
        "nome": "Oficina Rápida Centro",
        "servicos": ["colisao", "vidro"],
    },
    {
        "id": "of_003",
        "nome": "Master Auto Glass",
        "servicos": ["vidro", "pintura"],
    },
    {
        "id": "of_004",
        "nome": "Garage Plus Mecânica Especializada",
        "servicos": ["mecanica", "colisao"],
    },
]


@mcp.tool()
def buscar_oficinas_proximas(cep: str, tipo_servico: str) -> list[dict]:
    """Busca oficinas parceiras próximas a um CEP que atendem o tipo de serviço solicitado.

    Args:
        cep: CEP de referência do cliente (ex: "04538-133")
        tipo_servico: Tipo de serviço necessário. Valores válidos: colisao, vidro, pintura, mecanica
    """
    candidatas = [o for o in OFICINAS_MOCK if tipo_servico in o["servicos"]]
    resultado = []
    for oficina in candidatas:
        distancia = round(random.uniform(1.5, 9.5), 1)
        resultado.append(
            {
                "oficina_id": oficina["id"],
                "nome": oficina["nome"],
                "distancia_km": distancia,
                "atende_servico": tipo_servico,
            }
        )
    return sorted(resultado, key=lambda x: x["distancia_km"])[:3]


@mcp.tool()
def consultar_agenda_pericia(oficina_id: str, urgencia: str) -> list[dict]:
    """Consulta os próximos horários disponíveis para perícia ou vistoria em uma oficina parceira.

    Args:
        oficina_id: Identificador da oficina (retornado por buscar_oficinas_proximas)
        urgencia: Define o intervalo mínimo de antecedência. Valores válidos: normal, urgente
    """
    hoje = datetime.now()
    dias_minimos = 1 if urgencia == "urgente" else 2
    horarios_possiveis = ["09:00", "10:30", "13:00", "14:30", "16:00"]
    agendas = []
    for i in range(3):
        data = hoje + timedelta(days=dias_minimos + i)
        agendas.append(
            {
                "oficina_id": oficina_id,
                "data": data.strftime("%Y-%m-%d"),
                "horario": random.choice(horarios_possiveis),
            }
        )
    return agendas


if __name__ == "__main__":
    mcp.run(transport="stdio")
