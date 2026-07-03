"""
Servidor MCP standalone que simula o sistema de oficinas e peritos parceiros da ClaraSeg.

Transporte: streamable-http — roda isolado do resto do agente, em container
Docker próprio (ver workshop-mcp/Dockerfile), simulando um sistema de parceiro
externo acessado pela rede.

Autocontido de propósito: não importa nada de `ai-agent/src/` para poder ser
buildado como imagem Docker independente, sem as dependências do agente
principal (OpenAI, LangGraph etc). Lê a conexão MongoDB direto das variáveis
de ambiente.

Executar diretamente para testar: python workshop-mcp/workshop_server.py
"""
import os
import random
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "claraseg")
WORKSHOPS_COLLECTION = os.getenv("WORKSHOPS_COLLECTION", "workshops")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))

_client: MongoClient | None = None


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client[MONGODB_DB_NAME][WORKSHOPS_COLLECTION]


mcp = FastMCP("oficinas-parceiras", host=MCP_HOST, port=MCP_PORT)


@mcp.tool()
def buscar_oficinas_proximas(cep: str, tipo_servico: str) -> list[dict]:
    """Busca oficinas parceiras próximas a um CEP que atendem o tipo de serviço solicitado.

    Args:
        cep: CEP de referência do cliente (ex: "04538-133")
        tipo_servico: Tipo de serviço necessário. Valores válidos: colisao, vidro, pintura, mecanica
    """
    candidatas = _get_collection().find({"servicos": tipo_servico})
    resultado = []
    for oficina in candidatas:
        distancia = round(random.uniform(1.5, 9.5), 1)
        resultado.append(
            {
                "oficina_id": oficina["oficina_id"],
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


@mcp.tool()
def agendar_pericia(
    cliente_id: str,
    oficina_id: str,
    data: str,
    horario: str,
    tipo_servico: str,
    urgencia: str,
) -> dict:
    """Confirma o agendamento de uma perícia/vistoria em um horário retornado por
    consultar_agenda_pericia. Um cliente só pode ter um agendamento em aberto por vez —
    se já existir um, esta tool não cria um novo e retorna os dados do agendamento
    existente para que o cliente cancele ou altere antes de tentar novamente.

    Args:
        cliente_id: Identificador do cliente (campo customer_id do perfil).
        oficina_id: Identificador da oficina (retornado por buscar_oficinas_proximas).
        data: Data escolhida, formato YYYY-MM-DD (retornada por consultar_agenda_pericia).
        horario: Horário escolhido, formato HH:MM (retornado por consultar_agenda_pericia).
        tipo_servico: Tipo de serviço da perícia. Valores válidos: colisao, vidro, pintura, mecanica.
        urgencia: Urgência do agendamento. Valores válidos: normal, urgente.
    """
    collection = _get_collection()

    existente = collection.find_one(
        {"appointments": {"$elemMatch": {"cliente_id": cliente_id, "status": "confirmado"}}},
        {"oficina_id": 1, "nome": 1, "appointments.$": 1},
    )
    if existente:
        aberto = existente["appointments"][0]
        return {
            "sucesso": False,
            "erro": "cliente_ja_possui_agendamento_aberto",
            "agendamento_existente": {
                "agendamento_id": aberto["agendamento_id"],
                "oficina_id": existente["oficina_id"],
                "oficina_nome": existente["nome"],
                "data": aberto["data"],
                "horario": aberto["horario"],
                "servico": aberto["servico"],
                "urgencia": aberto["urgencia"],
            },
        }

    agendamento = {
        "agendamento_id": uuid.uuid4().hex[:8],
        "cliente_id": cliente_id,
        "data": data,
        "horario": horario,
        "servico": tipo_servico,
        "urgencia": urgencia,
        "status": "confirmado",
    }
    collection.update_one({"oficina_id": oficina_id}, {"$push": {"appointments": agendamento}})
    return {"sucesso": True, "agendamento": agendamento}


@mcp.tool()
def listar_agendamentos_cliente(cliente_id: str) -> list[dict]:
    """Lista todos os agendamentos de perícia do cliente (confirmados e cancelados),
    em qualquer oficina parceira.

    Args:
        cliente_id: Identificador do cliente (campo customer_id do perfil).
    """
    collection = _get_collection()
    oficinas = collection.find(
        {"appointments.cliente_id": cliente_id},
        {"oficina_id": 1, "nome": 1, "appointments": 1},
    )
    resultado = []
    for oficina in oficinas:
        for agendamento in oficina.get("appointments", []):
            if agendamento["cliente_id"] != cliente_id:
                continue
            resultado.append(
                {
                    "agendamento_id": agendamento["agendamento_id"],
                    "oficina_id": oficina["oficina_id"],
                    "oficina_nome": oficina["nome"],
                    "data": agendamento["data"],
                    "horario": agendamento["horario"],
                    "servico": agendamento["servico"],
                    "urgencia": agendamento["urgencia"],
                    "status": agendamento["status"],
                }
            )
    return resultado


@mcp.tool()
def cancelar_agendamento(cliente_id: str, agendamento_id: str) -> dict:
    """Cancela um agendamento de perícia em aberto do cliente.

    Args:
        cliente_id: Identificador do cliente (campo customer_id do perfil).
        agendamento_id: Identificador do agendamento (retornado por agendar_pericia
            ou listar_agendamentos_cliente).
    """
    collection = _get_collection()
    result = collection.update_one(
        {
            "appointments": {
                "$elemMatch": {
                    "agendamento_id": agendamento_id,
                    "cliente_id": cliente_id,
                    "status": "confirmado",
                }
            }
        },
        {"$set": {"appointments.$.status": "cancelado"}},
    )
    if result.matched_count == 0:
        return {"sucesso": False, "erro": "agendamento_nao_encontrado_ou_ja_cancelado"}
    return {"sucesso": True, "agendamento_id": agendamento_id}


@mcp.tool()
def alterar_agendamento(cliente_id: str, agendamento_id: str, nova_data: str, novo_horario: str) -> dict:
    """Altera a data/horário de um agendamento de perícia em aberto do cliente, para
    um novo horário retornado por consultar_agenda_pericia.

    Args:
        cliente_id: Identificador do cliente (campo customer_id do perfil).
        agendamento_id: Identificador do agendamento (retornado por agendar_pericia
            ou listar_agendamentos_cliente).
        nova_data: Nova data, formato YYYY-MM-DD.
        novo_horario: Novo horário, formato HH:MM.
    """
    collection = _get_collection()
    result = collection.update_one(
        {
            "appointments": {
                "$elemMatch": {
                    "agendamento_id": agendamento_id,
                    "cliente_id": cliente_id,
                    "status": "confirmado",
                }
            }
        },
        {"$set": {"appointments.$.data": nova_data, "appointments.$.horario": novo_horario}},
    )
    if result.matched_count == 0:
        return {"sucesso": False, "erro": "agendamento_nao_encontrado_ou_ja_cancelado"}
    return {"sucesso": True, "agendamento_id": agendamento_id, "data": nova_data, "horario": novo_horario}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
