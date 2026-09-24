"""
FinGuard - Agente 2: Análise de Risco e Compliance
Consulta o RAG da Política Interna para cruzar urgência com SLA regulatório,
avaliando risco financeiro, jurídico ou reputacional.
Usa modelo robusto (MODEL_RISCO) para análise complexa.
"""

import json
import time
import logging
from openai import OpenAI, DefaultHttpxClient

import config
from rag_engine import PolicyRAGEngine
from guardrails import sanitize_output
from finops import FinOpsTracker
from llm_json_utils import robust_json_loads

logger = logging.getLogger(__name__)


_NIVEL_ALIASES = {
    "moderado": "Médio", "moderate": "Médio", "medium": "Médio", "medio": "Médio",
    "baixo": "Baixo", "low": "Baixo",
    "alto": "Alto", "high": "Alto",
    "critico": "Crítico", "critical": "Crítico", "crítico": "Crítico",
}


def _normalize_risco(result: dict) -> dict:
    """Corrige mapeamentos de campos quando modelo retorna nomes alternativos."""
    if not result.get("nivel_risco"):
        for key in ("Risco", "risco", "nivel", "risk_level", "riskLevel", "nivel de risco"):
            val = result.get(key)
            if isinstance(val, str):
                result["nivel_risco"] = _NIVEL_ALIASES.get(val.lower().strip(), val)
                break
        if not result.get("nivel_risco") and result.get("riscos"):
            count = len(result["riscos"])
            result["nivel_risco"] = "Crítico" if count >= 4 else "Alto" if count >= 3 else "Médio" if count >= 2 else "Baixo"

    tipo = result.get("tipo_risco")
    if isinstance(tipo, str):
        result["tipo_risco"] = [t.strip() for t in tipo.replace("|", ",").split(",") if t.strip()]
    elif not tipo or tipo == ["Nenhum"]:
        # Tenta extrair de riscos[].tipo ou riscos[].nome quando modelo usa estrutura alternativa
        tipos_extraidos = []
        for item in result.get("riscos", []):
            for key in ("tipo", "nome", "name", "type"):
                val = item.get(key, "")
                if val and isinstance(val, str):
                    tipos_extraidos.append(val.strip())
                    break
        result["tipo_risco"] = tipos_extraidos if tipos_extraidos else ["Nenhum"]

    return result

RISCO_SYSTEM_PROMPT = """Você é um analista sênior de risco e compliance do sistema FinGuard.
Sua tarefa é avaliar uma reclamação já triada e determinar o nível de risco e conformidade.

Você receberá:
1. Os dados estruturados da triagem (categoria, produto, sentimento, urgência, resumo)
2. Trechos relevantes da Política Interna de Atendimento

RESPONDA SOMENTE COM UM OBJETO JSON VÁLIDO, exatamente neste formato:
{
  "nivel_risco": "Baixo",
  "tipo_risco": ["Financeiro", "Jurídico"],
  "sla_prazo": "24 horas",
  "acoes_imediatas": ["Acionar ouvidoria", "Contatar cliente em 2h"],
  "justificativa": "Explicação em 2-4 frases.",
  "recomendacao_escalonamento": true,
  "area_responsavel": "Ouvidoria"
}

VALORES PERMITIDOS:
- nivel_risco: exatamente um de "Baixo", "Médio", "Alto" ou "Crítico"
- tipo_risco: lista com um ou mais de "Financeiro", "Jurídico", "Reputacional", "Regulatório", "Fraude", "Nenhum"
- recomendacao_escalonamento: true ou false (booleano, sem aspas)

REGRAS:
- Cruze a urgência da triagem com os prazos e procedimentos da Política Interna.
- Se houver menção a Banco Central, Procon ou Justiça, o risco é AUTOMATICAMENTE Alto ou Crítico.
- Se houver indício de fraude, acione protocolo de Prevenção a Fraudes.
- Considere o canal de origem: Ouvidoria e Banco Central têm tratamento diferenciado.
- NÃO inclua dados pessoais do cliente na justificativa.
- NÃO adicione texto, explicação ou comentário fora do JSON.
- O JSON deve começar com { e terminar com } sem nenhum outro caractere."""


class RiscoAgent:
    """Agente responsável pela análise de risco e compliance."""

    def __init__(self, tracker: FinOpsTracker, rag: PolicyRAGEngine):
        self.tracker = tracker
        self.rag = rag
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            http_client=DefaultHttpxClient(verify=config.VERIFY_SSL),
        )
        self.model = config.MODEL_RISCO

    def process(self, triagem_result: dict) -> dict:
        """
        Analisa risco com base na triagem e consulta ao RAG.
        Pula se a reclamação foi bloqueada pelo guardrail de entrada.
        """
        complaint_id = triagem_result.get("id", "UNKNOWN")

        if triagem_result.get("blocked"):
            logger.info(f"[{complaint_id}] Pulando análise de risco (entrada bloqueada)")
            return {
                "id": complaint_id,
                "skipped": True,
                "reason": "Entrada bloqueada por guardrail",
            }

        if triagem_result.get("error"):
            logger.warning(f"[{complaint_id}] Pulando análise de risco (erro na triagem)")
            return {
                "id": complaint_id,
                "skipped": True,
                "reason": f"Erro na triagem: {triagem_result['error']}",
            }

        start_time = time.time()

        # Consulta RAG com base na urgência e produto
        urgencia = triagem_result.get("urgencia", "Média")
        produto = triagem_result.get("produto")
        canal = triagem_result.get("canal")

        rag_context = self.rag.get_sla_info(urgencia, produto)
        if canal:
            rag_context += "\n\n" + self.rag.query(f"canal {canal} procedimento", max_results=2)

        # Monta prompt com dados da triagem + contexto RAG
        user_prompt = f"""DADOS DA TRIAGEM:
- Categoria: {triagem_result.get('categoria', 'N/A')}
- Produto: {produto or 'Não Identificado'}
- Sentimento: {triagem_result.get('sentimento', 'N/A')}
- Urgência: {urgencia}
- Canal: {canal or 'N/A'}
- Resumo: {triagem_result.get('resumo', 'N/A')}

POLÍTICA INTERNA (trechos relevantes):
{rag_context}

Analise o risco e responda com o JSON solicitado."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": RISCO_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or ""
            usage = response.usage

            latency = time.time() - start_time
            if usage:
                self.tracker.record(
                    model=self.model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    latency_seconds=latency,
                    task_type="risco",
                    complaint_id=complaint_id,
                )

            # Parse JSON
            cleaned = content.strip()
            if not cleaned:
                raise ValueError("LLM retornou resposta vazia para análise de risco")

            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = robust_json_loads(cleaned)
            result = _normalize_risco(result)

            # Sanitiza textos de saída
            for field in ["justificativa", "acoes_imediatas"]:
                if field in result and isinstance(result[field], str):
                    result[field] = sanitize_output(result[field])
                elif field in result and isinstance(result[field], list):
                    result[field] = [sanitize_output(str(item)) for item in result[field]]

            result["id"] = complaint_id
            result["modelo_risco"] = self.model
            result["latencia_risco_s"] = round(latency, 3)

            logger.info(
                f"[{complaint_id}] Risco avaliado: {result.get('nivel_risco')} | "
                f"Tipo: {result.get('tipo_risco')}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"[{complaint_id}] Erro ao parsear JSON de risco: {e}")
            return {
                "id": complaint_id,
                "error": "Erro de parsing na resposta do modelo de risco",
                "raw_response": content[:500],
            }
        except Exception as e:
            logger.error(f"[{complaint_id}] Erro na análise de risco: {e}")
            return {"id": complaint_id, "error": str(e)}