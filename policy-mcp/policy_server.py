"""
Servidor MCP standalone responsável pela gestão de apólices (policies) dos
clientes da ClaraSeg — criação e atualização de apólices auto/residencial.

Transporte: streamable-http — roda isolado do resto do agente, em container
Docker próprio (ver policy-mcp/Dockerfile), no mesmo padrão do workshop-mcp.

Autocontido de propósito: não importa nada de `ai-agent/src/` para poder ser
buildado como imagem Docker independente, sem as dependências do agente
principal (OpenAI, LangGraph etc). Lê a conexão MongoDB direto das variáveis
de ambiente.

Opera na coleção `customer_profile` — a mesma que o agente usa para responder
perguntas sobre apólices/sinistros — onde cada documento de cliente embute
seu array `policies`.

Executar diretamente para testar: python policy-mcp/policy_server.py
"""
import os
import random
from datetime import datetime

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "claraseg")
CUSTOMER_PROFILE_COLLECTION = os.getenv("CUSTOMER_PROFILE_COLLECTION", "customer_profile")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

# Tipos de apólice suportados -> campo específico que cada tipo carrega.
TIPOS_VALIDOS = {"auto": "vehicle", "residencial": "address"}
PREFIXO_POLICY_ID = {"auto": "POL-AUTO", "residencial": "POL-RES"}

_client: MongoClient | None = None


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client[MONGODB_DB_NAME][CUSTOMER_PROFILE_COLLECTION]


def _renovacao_daqui_um_ano() -> str:
    """Data de renovação: hoje + 1 ano (ex: 2026-07-01 -> 2027-07-01)."""
    hoje = datetime.now()
    try:
        proxima = hoje.replace(year=hoje.year + 1)
    except ValueError:
        # 29/02 em ano bissexto não existe no ano seguinte
        proxima = hoje.replace(year=hoje.year + 1, day=28)
    return proxima.strftime("%Y-%m-%d")


def _gerar_policy_id(collection, tipo: str) -> str:
    prefixo = PREFIXO_POLICY_ID[tipo]
    while True:
        candidato = f"{prefixo}-{random.randint(1000, 9999)}"
        if collection.find_one({"policies.policy_id": candidato}) is None:
            return candidato


mcp = FastMCP("gestao-apolices", host=MCP_HOST, port=MCP_PORT)


@mcp.tool()
def listar_apolices_cliente(cliente_id: str) -> dict:
    """Lista todas as apólices (auto e residencial) de um cliente.

    Args:
        cliente_id: Identificador do cliente (campo customer_id do perfil).
    """
    cliente = _get_collection().find_one({"customer_id": cliente_id}, {"policies": 1})
    if cliente is None:
        return {"sucesso": False, "erro": "cliente_nao_encontrado"}
    return {"sucesso": True, "apolices": cliente.get("policies", [])}


@mcp.tool()
def criar_apolice(cliente_id: str, tipo: str, vehicle: str | None = None, address: str | None = None) -> dict:
    """Cria uma nova apólice para o cliente, do tipo auto ou residencial.
    A apólice nasce sempre com status "pending" e data de renovação
    (renewal_date) igual à data atual + 1 ano — esses dois campos não são
    informados pelo chamador, são sempre calculados por esta tool.

    Args:
        cliente_id: Identificador do cliente (campo customer_id do perfil).
        tipo: Tipo da apólice. Valores válidos: auto, residencial.
        vehicle: Obrigatório se tipo="auto". Descrição do veículo (ex: "Honda Civic 2022").
        address: Obrigatório se tipo="residencial". Endereço do imóvel segurado.
    """
    if tipo not in TIPOS_VALIDOS:
        return {"sucesso": False, "erro": "tipo_invalido", "tipos_validos": list(TIPOS_VALIDOS)}

    if tipo == "auto" and not vehicle:
        return {"sucesso": False, "erro": "vehicle_obrigatorio_para_tipo_auto"}
    if tipo == "residencial" and not address:
        return {"sucesso": False, "erro": "address_obrigatorio_para_tipo_residencial"}

    collection = _get_collection()
    if collection.find_one({"customer_id": cliente_id}) is None:
        return {"sucesso": False, "erro": "cliente_nao_encontrado"}

    nova_apolice = {
        "policy_id": _gerar_policy_id(collection, tipo),
        "type": tipo,
        "status": "pending",
        "renewal_date": _renovacao_daqui_um_ano(),
    }
    if tipo == "auto":
        nova_apolice["vehicle"] = vehicle
    else:
        nova_apolice["address"] = address

    collection.update_one({"customer_id": cliente_id}, {"$push": {"policies": nova_apolice}})
    return {"sucesso": True, "apolice": nova_apolice}


@mcp.tool()
def atualizar_apolice(
    cliente_id: str,
    apolice_id: str,
    vehicle: str | None = None,
    address: str | None = None,
) -> dict:
    """Atualiza os dados de uma apólice existente do cliente (veículo, se for
    apólice auto, ou endereço, se for residencial). Toda atualização força
    status="pending" e renova a data de renovação (renewal_date) para a data
    atual + 1 ano, independentemente de quais campos foram alterados.

    Args:
        cliente_id: Identificador do cliente (campo customer_id do perfil).
        apolice_id: Identificador da apólice a atualizar (campo policy_id).
        vehicle: Novo valor do veículo. Só válido em apólices do tipo auto.
        address: Novo valor do endereço. Só válido em apólices do tipo residencial.
    """
    if vehicle is None and address is None:
        return {"sucesso": False, "erro": "nenhum_campo_informado"}

    collection = _get_collection()
    cliente = collection.find_one(
        {"customer_id": cliente_id, "policies.policy_id": apolice_id},
        {"policies.$": 1},
    )
    if cliente is None:
        return {"sucesso": False, "erro": "cliente_ou_apolice_nao_encontrado"}

    apolice_atual = cliente["policies"][0]
    tipo = apolice_atual["type"]
    if vehicle is not None and tipo != "auto":
        return {"sucesso": False, "erro": "campo_vehicle_nao_aplicavel_ao_tipo_da_apolice", "tipo_apolice": tipo}
    if address is not None and tipo != "residencial":
        return {"sucesso": False, "erro": "campo_address_nao_aplicavel_ao_tipo_da_apolice", "tipo_apolice": tipo}

    campos_set = {
        "policies.$.status": "pending",
        "policies.$.renewal_date": _renovacao_daqui_um_ano(),
    }
    if vehicle is not None:
        campos_set["policies.$.vehicle"] = vehicle
    if address is not None:
        campos_set["policies.$.address"] = address

    collection.update_one(
        {"customer_id": cliente_id, "policies.policy_id": apolice_id},
        {"$set": campos_set},
    )
    apolice_atualizada = {**apolice_atual, **{campo.split(".")[-1]: valor for campo, valor in campos_set.items()}}
    return {"sucesso": True, "apolice": apolice_atualizada}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
