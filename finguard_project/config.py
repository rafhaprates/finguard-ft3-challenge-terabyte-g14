"""
FinGuard - Configurações Globais
Carrega variáveis de ambiente e expõe constantes para todo o projeto.

Suporta dois provedores de LLM via variável LLM_PROVIDER:
  - "zup"   : AI Gateway Zup (LiteLLM proxy) com Claude Haiku/Sonnet via Bedrock
              Credenciais carregadas do ~/.zshrc: KEY_FT, LITELLM_PROXY_URL,
              MODEL_HAIKU_FT, MODEL_SONNET_FT, BUDGET_FT
  - "ollama": Ollama local (http://localhost:11434/v1) com modelos locais
              Modelos configurados via OLLAMA_MODEL_LIGHT e OLLAMA_MODEL_HEAVY

Default: "zup" (mantém comportamento atual).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env do diretório do projeto (opcional, fallback para env vars do shell)
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")


def _get_env(key: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        raise EnvironmentError(f"Variável de ambiente obrigatória não definida: {key}")
    return value or ""


# --- Provider Selection ---
# "zup" ou "ollama". Default "zup" para manter compatibilidade com o desafio.
LLM_PROVIDER = _get_env("LLM_PROVIDER", default="zup").lower().strip()

# --- Zup AI Gateway Configuration ---
KEY_FT = _get_env("KEY_FT", default="")
LITELLM_PROXY_URL = _get_env(
    "LITELLM_PROXY_URL",
    default="https://dx-ai-gateway.platform.sbox.zupcloud.corp",
)
KEY_ALIAS_FT = _get_env("KEY_ALIAS_FT", default="")
BUDGET_FT = float(_get_env("BUDGET_FT", default="0.0"))

# --- Ollama Local Configuration ---
OLLAMA_BASE_URL = _get_env("OLLAMA_BASE_URL", default="http://localhost:11434/v1")
OLLAMA_MODEL_LIGHT = _get_env("OLLAMA_MODEL_LIGHT", default="qwen2.5:0.5b")
OLLAMA_MODEL_HEAVY = _get_env("OLLAMA_MODEL_HEAVY", default="qwen2.5:0.5b")

# --- Unified API Configuration (resolved by provider) ---
if LLM_PROVIDER == "ollama":
    OPENAI_API_KEY = "ollama"  # Ollama aceita qualquer string como api_key
    OPENAI_BASE_URL = OLLAMA_BASE_URL
    VERIFY_SSL = True  # localhost não precisa de verify=False
else:
    # Zup AI Gateway (default)
    OPENAI_API_KEY = KEY_FT
    OPENAI_BASE_URL = LITELLM_PROXY_URL
    VERIFY_SSL = False  # sandbox Zup usa certificado autoassinado

# --- Model Routing (FinOps) ---
# Resolve modelos conforme o provider ativo.
if LLM_PROVIDER == "ollama":
    MODEL_TRIAGEM = OLLAMA_MODEL_LIGHT
    MODEL_RISCO = OLLAMA_MODEL_HEAVY
    MODEL_RELATORIO = OLLAMA_MODEL_HEAVY
else:
    # Zup: Haiku (leve) para triagem; Sonnet (robusto) para risco e relatório.
    MODEL_TRIAGEM = _get_env(
        "MODEL_HAIKU_FT", default="bedrock-anthropic-claude-haiku-4-5"
    )
    MODEL_RISCO = _get_env(
        "MODEL_SONNET_FT", default="bedrock-anthropic-claude-sonnet-4-5"
    )
    MODEL_RELATORIO = _get_env(
        "MODEL_SONNET_FT", default="bedrock-anthropic-claude-sonnet-4-5"
    )

# --- Custos estimados por 1M tokens (USD) ---
# Para Ollama local o custo é zero (infra própria); mantemos valores para FinOps tracking.
if LLM_PROVIDER == "ollama":
    COST_INPUT_LIGHT = float(_get_env("COST_INPUT_LIGHT", default="0.00"))
    COST_OUTPUT_LIGHT = float(_get_env("COST_OUTPUT_LIGHT", default="0.00"))
    COST_INPUT_HEAVY = float(_get_env("COST_INPUT_HEAVY", default="0.00"))
    COST_OUTPUT_HEAVY = float(_get_env("COST_OUTPUT_HEAVY", default="0.00"))
else:
    # Claude Haiku 4.5 / Sonnet 4.5 via Bedrock
    COST_INPUT_LIGHT = float(_get_env("COST_INPUT_LIGHT", default="0.80"))
    COST_OUTPUT_LIGHT = float(_get_env("COST_OUTPUT_LIGHT", default="4.00"))
    COST_INPUT_HEAVY = float(_get_env("COST_INPUT_HEAVY", default="3.00"))
    COST_OUTPUT_HEAVY = float(_get_env("COST_OUTPUT_HEAVY", default="15.00"))

# --- Caminhos dos Artefatos ---
_ARTIFACTS_DIR = (_PROJECT_ROOT.parent / "artifacts").resolve()
DATASET_PATH = _ARTIFACTS_DIR / "dataset_finguard_desafio_3 (4).csv"
POLICY_PDF_PATH = _ARTIFACTS_DIR / "KS_POLITICA_INTERNA (4).pdf"

# --- Logs ---
LOG_LEVEL = _get_env("LOG_LEVEL", default="INFO")

# --- Diretórios de Saída ---
OUTPUT_DIR = _PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_FILE = OUTPUT_DIR / "finguard_execution.log"
RESULTS_JSON = OUTPUT_DIR / "resultados_analise.json"
REPORT_HTML = OUTPUT_DIR / "relatorio_executivo.html"
ADR_HTML = OUTPUT_DIR / "adr.html"
FINOPS_REPORT = OUTPUT_DIR / "finops_report.json"