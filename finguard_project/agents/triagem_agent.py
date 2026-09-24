"""
FinGuard - Agente 1: Triagem
Recebe o texto bruto da reclamação, sanitiza via guardrail e extrai:
Categoria, Produto, Sentimento, Nível de Urgência e Resumo Padronizado.
Usa modelo leve (MODEL_TRIAGEM) para otimização de custos.
"""

import json
import time
import logging
from openai import OpenAI, DefaultHttpxClient

import config
from guardrails import check_input_guardrails, sanitize_output, BLOCK_MESSAGE
from finops import FinOpsTracker
from llm_json_utils import robust_json_loads

logger = logging.getLogger(__name__)

TRIAGEM_SYSTEM_PROMPT = """Você é um analista de triagem de reclamações bancárias do sistema FinGuard.
Sua tarefa é analisar o texto de uma reclamação de cliente e extrair informações estruturadas.

RESPONDA SOMENTE COM UM OBJETO JSON VÁLIDO, exatamente neste formato:
{
  "categoria": "Cobrança Indevida",
  "produto": "Cartão de Crédito",
  "sentimento": "Negativo",
  "urgencia": "Alta",
  "resumo": "Cliente relata cobrança indevida na fatura do cartão de crédito após cancelamento do serviço. Solicita estorno imediato e ameaça registrar ocorrência no Procon."
}

VALORES PERMITIDOS:
- categoria: exatamente um de "Cobrança Indevida", "Atendimento", "Fraude/Segurança", "Produto/Serviço", "Cancelamento", "Outros"
- produto: exatamente um de "Cartão de Crédito", "Conta Corrente", "Empréstimo", "Investimentos", "Seguros", "Não Identificado"
- sentimento: exatamente um de "Positivo", "Neutro", "Negativo", "Crítico"
- urgencia: exatamente um de "Baixa", "Média", "Alta", "Crítica"

REGRAS:
- O resumo deve ser escrito em tom profissional, sem termos impróprios ou linguagem informal.
- Se o produto não estiver claro no texto, use "Não Identificado".
- Urgência Crítica: indícios de fraude, menção a Banco Central/Procon/Justiça, risco à segurança.
- Urgência Alta: valores significativos, múltiplas tentativas sem resolução, ameaça de escalação.
- Urgência Média: impacto financeiro moderado, problemas recorrentes.
- Urgência Baixa: dúvidas operacionais, insatisfações leves.
- NÃO inclua dados pessoais (CPF, número de conta, cartão) no resumo.
- NÃO adicione texto, explicação ou comentário fora do JSON.
- O JSON deve começar com { e terminar com } sem nenhum outro caractere."""


class TriagemAgent:
    """Agente responsável pela triagem inicial de reclamações."""

    def __init__(self, tracker: FinOpsTracker):
        self.tracker = tracker
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            http_client=DefaultHttpxClient(verify=config.VERIFY_SSL),
        )
        self.model = config.MODEL_TRIAGEM

    def process(self, complaint_id: str, raw_text: str) -> dict:
        """
        Processa uma reclamação bruta e retorna análise estruturada.
        Retorna dict com 'blocked' = True se guardrail bloquear.
        """
        start_time = time.time()

        # Input Guardrail
        guard_result = check_input_guardrails(raw_text)
        if not guard_result.passed:
            logger.warning(f"[{complaint_id}] Bloqueado por input guardrail: {guard_result.reason}")
            return {
                "id": complaint_id,
                "blocked": True,
                "block_reason": guard_result.reason,
                "mensagem": BLOCK_MESSAGE,
            }

        # Chamada ao LLM
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": TRIAGEM_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Reclamação:\n{raw_text}"},
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or ""
            usage = response.usage

            # Registra no FinOps
            latency = time.time() - start_time
            if usage:
                self.tracker.record(
                    model=self.model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    latency_seconds=latency,
                    task_type="triagem",
                    complaint_id=complaint_id,
                )

            # Parse do JSON
            # Remove possíveis markdown fences
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = robust_json_loads(cleaned)

            # Sanitiza o resumo na saída
            if "resumo" in result:
                result["resumo"] = sanitize_output(result["resumo"])

            result["id"] = complaint_id
            result["blocked"] = False
            result["modelo_triagem"] = self.model
            result["latencia_triagem_s"] = round(latency, 3)

            logger.info(f"[{complaint_id}] Triagem concluída: {result.get('categoria')} | {result.get('urgencia')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"[{complaint_id}] Erro ao parsear JSON da triagem: {e}")
            return {
                "id": complaint_id,
                "blocked": False,
                "error": "Erro de parsing na resposta do modelo",
                "raw_response": content[:500],
            }
        except Exception as e:
            logger.error(f"[{complaint_id}] Erro na triagem: {e}")
            return {
                "id": complaint_id,
                "blocked": False,
                "error": str(e),
            }