from pathlib import Path

# Configuração do servidor MCP de oficinas. Usado em agent.py para iniciar o
# subprocesso via stdio dentro do contexto assíncrono de cada invocação.
MCP_SERVER_CONFIG = {
    "oficinas": {
        "command": "python",
        "args": [str(Path(__file__).parent.parent.parent / "mcp_servers" / "workshop_server.py")],
        "transport": "stdio",
    }
}
