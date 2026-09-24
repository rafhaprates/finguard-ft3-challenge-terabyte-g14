"""
FinGuard - Orquestrador do Fluxo Multi-Agente
Coordena a execução sequencial dos agentes (Triagem → Risco → Relatório),
gerencia logs de execução e integra o sistema de FinOps.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import config
from finops import FinOpsTracker
from rag_engine import PolicyRAGEngine
from agents.triagem_agent import TriagemAgent
from agents.risco_agent import RiscoAgent
from agents.relatorio_agent import RelatorioAgent

logger = logging.getLogger(__name__)


class FinGuardOrchestrator:
    """Orquestra o pipeline completo de análise de reclamações."""

    def __init__(self):
        self.tracker = FinOpsTracker()
        self.rag = PolicyRAGEngine()
        self.triagem_agent = TriagemAgent(self.tracker)
        self.risco_agent = RiscoAgent(self.tracker, self.rag)
        self.relatorio_agent = RelatorioAgent(self.tracker)
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configura logging para arquivo e console."""
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        handlers = [
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ]
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL, logging.INFO),
            format=log_format,
            handlers=handlers,
            force=True,
        )

    def process_complaint(self, complaint_id: str, raw_text: str, canal: str | None = None) -> dict:
        """
        Processa uma única reclamação através do pipeline completo:
        1. Triagem (com input guardrail)
        2. Análise de Risco (com RAG)
        3. Retorna resultado consolidado
        """
        start_time = time.time()
        logger.info(f"[{complaint_id}] === INÍCIO DO PROCESSAMENTO ===")

        # Etapa 1: Triagem
        logger.info(f"[{complaint_id}] Etapa 1/3: Triagem")
        triagem_result = self.triagem_agent.process(complaint_id, raw_text)
        if canal:
            triagem_result["canal"] = canal

        # Se bloqueado ou erro, pula risco
        if triagem_result.get("blocked") or triagem_result.get("error"):
            logger.warning(f"[{complaint_id}] Pipeline interrompido na triagem")
            return {**triagem_result, "analise_risco": {"skipped": True}}

        # Etapa 2: Análise de Risco
        logger.info(f"[{complaint_id}] Etapa 2/3: Análise de Risco")
        risco_result = self.risco_agent.process(triagem_result)

        # Consolida resultado
        consolidated = {**triagem_result, "analise_risco": risco_result}

        elapsed = time.time() - start_time
        logger.info(
            f"[{complaint_id}] === PROCESSAMENTO CONCLUÍDO em {elapsed:.2f}s ==="
        )

        return consolidated

    def process_batch(self, complaints: list[dict]) -> dict:
        """
        Processa um lote de reclamações e gera relatório gerencial.

        Args:
            complaints: Lista de dicts com 'id', 'texto_reclamacao' e opcionalmente 'canal'.

        Returns:
            Relatório gerencial completo.
        """
        batch_start = time.time()
        total = len(complaints)
        logger.info(f"=== INICIANDO LOTE DE {total} RECLAMAÇÕES ===")

        all_results = []
        for i, complaint in enumerate(complaints, 1):
            complaint_id = complaint.get("id", f"REC-{i:05d}")
            raw_text = complaint.get("texto_reclamacao", "")
            canal = complaint.get("canal")

            logger.info(f"Processando {i}/{total}: {complaint_id}")
            result = self.process_complaint(complaint_id, raw_text, canal)
            all_results.append(result)

        # Etapa 3: Relatório Gerencial
        logger.info("Etapa 3/3: Gerando Relatório Gerencial")
        report = self.relatorio_agent.generate(all_results)

        # Salva resultados individuais
        results_path = config.RESULTS_JSON
        results_path.write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Resultados salvos em: {results_path}")

        # Salva relatório FinOps
        self.tracker.save_report()

        batch_elapsed = time.time() - batch_start
        logger.info(
            f"=== LOTE CONCLUÍDO: {total} reclamações em {batch_elapsed:.1f}s | "
            f"Custo total: USD {self.tracker.total_cost_usd:.4f} ==="
        )

        return report