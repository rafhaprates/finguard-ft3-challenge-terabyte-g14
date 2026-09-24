"""
FinGuard - Script de Execução Principal
Carrega o dataset CSV, processa todas as reclamações via orquestrador multi-agente,
gera relatório executivo (HTML), resultados (JSON) e documentação ADR (HTML).

Uso:
    source finguard_env/bin/activate
    cd finguard_project
    python main.py [--limit N] [--sample]
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

import config
from orchestrator import FinGuardOrchestrator
from adr_generator import generate_adr

logger = logging.getLogger(__name__)


def load_dataset(path: Path, limit: int | None = None, sample: bool = False) -> list[dict]:
    """Carrega o dataset CSV e retorna lista de dicts."""
    if not path.exists():
        logger.error(f"Dataset não encontrado: {path}")
        sys.exit(1)

    # Lê com encoding utf-8-sig para lidar com BOM do Excel
    df = pd.read_csv(str(path), encoding="utf-8-sig")

    # Valida colunas obrigatórias
    required_cols = {"id", "texto_reclamacao"}
    missing = required_cols - set(df.columns)
    if missing:
        logger.error(f"Colunas obrigatórias ausentes no dataset: {missing}")
        sys.exit(1)

    # Preenche valores nulos
    df["texto_reclamacao"] = df["texto_reclamacao"].fillna("")
    df["canal"] = df.get("canal", pd.Series([""] * len(df))).fillna("")
    df["produto"] = df.get("produto", pd.Series([""] * len(df))).fillna("")

    records = df.to_dict(orient="records")

    if sample and len(records) > 10:
        records = records[:10]
        logger.info(f"Modo amostra: processando apenas {len(records)} reclamações")
    elif limit and limit < len(records):
        records = records[:limit]
        logger.info(f"Limite aplicado: processando {len(records)} de {len(df)} reclamações")

    logger.info(f"Dataset carregado: {len(records)} reclamações de {path.name}")
    return records


def print_summary(report: dict) -> None:
    """Imprime resumo da execução no console."""
    stats = report.get("estatisticas", {})
    finops = report.get("finops", {})
    meta = report.get("metadata", {})

    print("\n" + "=" * 60)
    print("🛡️  FinGuard — Resumo da Execução")
    print("=" * 60)
    print(f"  Reclamações processadas: {stats.get('total_processadas', 0)}")
    print(f"  Bloqueadas por guardrail: {stats.get('bloqueadas', 0)}")
    print(f"  Erros: {stats.get('erros', 0)}")
    print(f"  Tempo total: {finops.get('elapsed_seconds', 0):.1f}s")
    print(f"  Custo estimado: USD {finops.get('total_cost_usd', 0):.4f}")
    print(f"  Tokens consumidos: {finops.get('total_tokens', 0):,}")
    print(f"  Chamadas LLM: {finops.get('total_calls', 0)}")
    print("-" * 60)
    print("  📁 Artefatos gerados:")
    print(f"     Resultados JSON: {config.RESULTS_JSON}")
    print(f"     Dashboard HTML:  {config.REPORT_HTML}")
    print(f"     Relatório FinOps:{config.FINOPS_REPORT}")
    print(f"     ADR HTML:        {config.ADR_HTML}")
    print(f"     Logs:            {config.LOG_FILE}")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="FinGuard - Pipeline de Análise de Reclamações")
    parser.add_argument("--limit", type=int, default=None, help="Limita o número de reclamações processadas")
    parser.add_argument("--sample", action="store_true", help="Processa apenas 10 reclamações (modo teste)")
    args = parser.parse_args()

    start_time = time.time()

    # Carrega dataset
    complaints = load_dataset(config.DATASET_PATH, limit=args.limit, sample=args.sample)

    if not complaints:
        logger.error("Nenhuma reclamação para processar.")
        sys.exit(1)

    # Inicializa orquestrador e processa lote
    orchestrator = FinGuardOrchestrator()
    report = orchestrator.process_batch(complaints)

    # Gera ADR
    logger.info("Gerando documentação ADR...")
    generate_adr()

    # Imprime resumo
    elapsed = time.time() - start_time
    print_summary(report)
    logger.info(f"Execução completa em {elapsed:.1f}s")


if __name__ == "__main__":
    main()