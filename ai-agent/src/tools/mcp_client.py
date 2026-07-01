from src.config import WORKSHOP_MCP_URL

# Configuração do servidor MCP de oficinas. Usado em agent.py para conectar
# ao servidor via HTTP — roda isolado, em container Docker próprio
# (ver workshop-mcp/Dockerfile), simulando um sistema de parceiro externo.
MCP_SERVER_CONFIG = {
    "oficinas": {
        "url": WORKSHOP_MCP_URL,
        "transport": "http",
    }
}
