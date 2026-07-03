from src.config import WORKSHOP_MCP_URL, POLICY_MCP_URL

# Configuração dos servidores MCP externos. Usado em agent.py para conectar
# via HTTP — cada um roda isolado, em container Docker próprio (ver
# workshop-mcp/Dockerfile e policy-mcp/Dockerfile), simulando sistemas de
# parceiro/backend externos ao agente.
MCP_SERVER_CONFIG = {
    "oficinas": {
        "url": WORKSHOP_MCP_URL,
        "transport": "http",
    },
    "apolices": {
        "url": POLICY_MCP_URL,
        "transport": "http",
    },
}
