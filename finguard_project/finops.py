"""
FinGuard - FinOps: Rastreamento de Tokens e Estimativa de Custos
Implementa contador de tokens por chamada, roteamento inteligente de modelos
e cálculo de custo total do lote processado.
"""

import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import config


@dataclass
class TokenUsage:
    """Registro de uso de tokens para uma única chamada LLM."""
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    task_type: str = ""
    complaint_id: str = ""


class FinOpsTracker:
    """Rastreia consumo de tokens e custos em tempo real."""

    def __init__(self):
        self._records: list[TokenUsage] = []
        self._start_time = time.time()

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
        task_type: str = "",
        complaint_id: str = "",
    ) -> TokenUsage:
        """Registra uma chamada LLM e calcula o custo estimado."""
        is_light = self._is_light_model(model)

        if is_light:
            input_cost = (prompt_tokens / 1_000_000) * config.COST_INPUT_LIGHT
            output_cost = (completion_tokens / 1_000_000) * config.COST_OUTPUT_LIGHT
        else:
            input_cost = (prompt_tokens / 1_000_000) * config.COST_INPUT_HEAVY
            output_cost = (completion_tokens / 1_000_000) * config.COST_OUTPUT_HEAVY

        usage = TokenUsage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=input_cost + output_cost,
            latency_seconds=latency_seconds,
            task_type=task_type,
            complaint_id=complaint_id,
        )
        self._records.append(usage)
        return usage

    @staticmethod
    def _is_light_model(model: str) -> bool:
        """Determina se o modelo é 'leve' baseado no nome/configuração."""
        light_indicators = ["mini", "haiku", "flash", "nano", "small", "3.5"]
        model_lower = model.lower()
        return any(ind in model_lower for ind in light_indicators)

    def get_routing_model(self, task_type: str) -> str:
        """Retorna o modelo apropriado para o tipo de tarefa (Model Routing)."""
        if task_type == "triagem":
            return config.MODEL_TRIAGEM
        elif task_type == "risco":
            return config.MODEL_RISCO
        elif task_type == "relatorio":
            return config.MODEL_RELATORIO
        return config.MODEL_TRIAGEM  # fallback para leve

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self._records)

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self._records)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(r.prompt_tokens for r in self._records)

    @property
    def total_completion_tokens(self) -> int:
        return sum(r.completion_tokens for r in self._records)

    @property
    def total_calls(self) -> int:
        return len(self._records)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self._start_time

    def summary(self) -> dict:
        """Retorna resumo consolidado de custos e uso."""
        by_task = {}
        for r in self._records:
            key = r.task_type or "unknown"
            if key not in by_task:
                by_task[key] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            by_task[key]["calls"] += 1
            by_task[key]["tokens"] += r.total_tokens
            by_task[key]["cost_usd"] += r.cost_usd

        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "cost_per_complaint": round(
                self.total_cost_usd / max(len(set(r.complaint_id for r in self._records)), 1), 6
            ),
            "by_task_type": by_task,
        }

    def save_report(self, path: Path | None = None) -> None:
        """Salva relatório detalhado em JSON."""
        output_path = path or config.FINOPS_REPORT
        report = {
            "summary": self.summary(),
            "records": [
                {
                    "complaint_id": r.complaint_id,
                    "task_type": r.task_type,
                    "model": r.model,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "total_tokens": r.total_tokens,
                    "cost_usd": round(r.cost_usd, 6),
                    "latency_seconds": round(r.latency_seconds, 3),
                }
                for r in self._records
            ],
        }
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))