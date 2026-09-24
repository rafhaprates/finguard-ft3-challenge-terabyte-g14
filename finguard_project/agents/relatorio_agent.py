"""
FinGuard - Agente 3: Relatório Gerencial
Compila todas as análises em um JSON padronizado e gera dashboard executivo
formatado em HTML com estatísticas gerais do lote de reclamações.
"""

import json
import time
import logging
from datetime import datetime
from collections import Counter
from pathlib import Path
from llm_json_utils import robust_json_loads
from openai import OpenAI, DefaultHttpxClient

import config
from guardrails import sanitize_output
from finops import FinOpsTracker

logger = logging.getLogger(__name__)

RELATORIO_SYSTEM_PROMPT = """Você é um gerente de operações do FinGuard gerando um relatório executivo.
Receberá um resumo estatístico das reclamações processadas e deve gerar recomendações acionáveis.

RESPONDA APENAS COM UM JSON VÁLIDO:
{
  "resumo_executivo": "parágrafo de 3-5 frases resumindo o cenário geral",
  "recomendacoes": ["lista de 3 a 5 recomendações específicas e acionáveis"],
  "alertas_criticos": ["lista de pontos de atenção imediata"],
  "tendencias": "identificação de padrões ou tendências nos dados"
}

Use tom profissional, orientado a dados e focado em ações concretas.
RESPONDA SOMENTE COM O JSON."""


class RelatorioAgent:
    """Agente responsável pela compilação do relatório gerencial."""

    def __init__(self, tracker: FinOpsTracker):
        self.tracker = tracker
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            http_client=DefaultHttpxClient(verify=config.VERIFY_SSL),
        )
        self.model = config.MODEL_RELATORIO

    def generate(self, all_results: list[dict]) -> dict:
        """
        Gera relatório gerencial consolidado a partir de todos os resultados.
        """
        start_time = time.time()

        # Compila estatísticas
        stats = self._compile_statistics(all_results)

        # Chama LLM para insights executivos
        stats_text = json.dumps(stats, indent=2, ensure_ascii=False)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": RELATORIO_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Estatísticas do lote processado:\n{stats_text}\n\nGere o relatório executivo.",
                    },
                ],
                temperature=0.3,
                max_tokens=1000,
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
                    task_type="relatorio",
                    complaint_id="BATCH",
                )

            # Parse JSON
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            executive_insights = robust_json_loads(cleaned)

            # Sanitiza
            for key in ["resumo_executivo", "tendencias"]:
                if key in executive_insights and isinstance(executive_insights[key], str):
                    executive_insights[key] = sanitize_output(executive_insights[key])
            for key in ["recomendacoes", "alertas_criticos"]:
                if key in executive_insights and isinstance(executive_insights[key], list):
                    executive_insights[key] = [sanitize_output(str(item)) for item in executive_insights[key]]

        except Exception as e:
            logger.error(f"Erro ao gerar insights executivos: {e}")
            executive_insights = {
                "resumo_executivo": "Não foi possível gerar insights automáticos.",
                "recomendacoes": ["Revisar manualmente as reclamações críticas."],
                "alertas_criticos": [],
                "tendencias": "Análise indisponível.",
            }

        report = {
            "metadata": {
                "gerado_em": datetime.now().isoformat(),
                "total_reclamacoes": len(all_results),
                "modelo_relatorio": self.model,
                "latencia_relatorio_s": round(time.time() - start_time, 3),
            },
            "estatisticas": stats,
            "insights_executivos": executive_insights,
            "finops": self.tracker.summary(),
        }

        # Gera HTML do dashboard
        html_path = self._generate_html_dashboard(report, all_results)
        report["dashboard_html"] = str(html_path)

        logger.info(f"Relatório gerado: {len(all_results)} reclamações processadas")
        return report

    def _compile_statistics(self, results: list[dict]) -> dict:
        """Compila estatísticas agregadas dos resultados."""
        blocked = sum(1 for r in results if r.get("blocked"))
        errors = sum(1 for r in results if r.get("error") and not r.get("blocked"))
        processed = [r for r in results if not r.get("blocked") and not r.get("error")]

        categorias = Counter(r.get("categoria", "N/A") for r in processed)
        produtos = Counter(r.get("produto", "N/A") for r in processed)
        sentimentos = Counter(r.get("sentimento", "N/A") for r in processed)
        urgencias = Counter(r.get("urgencia", "N/A") for r in processed)

        riscos = Counter()
        tipos_risco = Counter()
        for r in processed:
            risco_data = r.get("analise_risco", {})
            if risco_data and not risco_data.get("skipped"):
                riscos[risco_data.get("nivel_risco", "N/A")] += 1
                tipo = risco_data.get("tipo_risco", [])
                if isinstance(tipo, list):
                    for t in tipo:
                        tipos_risco[t] += 1
                elif isinstance(tipo, str):
                    tipos_risco[tipo] += 1

        criticos = [
            {
                "id": r.get("id"),
                "categoria": r.get("categoria"),
                "produto": r.get("produto"),
                "urgencia": r.get("urgencia"),
                "resumo": r.get("resumo"),
                "nivel_risco": r.get("analise_risco", {}).get("nivel_risco"),
                "justificativa_risco": r.get("analise_risco", {}).get("justificativa"),
            }
            for r in processed
            if r.get("analise_risco", {}).get("nivel_risco") in ("Alto", "Crítico")
        ]

        return {
            "total_processadas": len(processed),
            "bloqueadas": blocked,
            "erros": errors,
            "por_categoria": dict(categorias.most_common()),
            "por_produto": dict(produtos.most_common()),
            "por_sentimento": dict(sentimentos.most_common()),
            "por_urgencia": dict(urgencias.most_common()),
            "por_nivel_risco": dict(riscos.most_common()),
            "por_tipo_risco": dict(tipos_risco.most_common()),
            "reclamacoes_criticas": criticos[:20],
        }

    def _generate_html_dashboard(self, report: dict, all_results: list[dict]) -> Path:
        """Gera dashboard HTML estilizado e responsivo."""
        stats = report["estatisticas"]
        insights = report["insights_executivos"]
        finops = report["finops"]

        # Cores temáticas financeiras (azul escuro, verde, âmbar)
        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FinGuard — Dashboard Executivo</title>
<style>
  :root {{
    --bg: #f8fafc; --card: #ffffff; --text: #1e293b; --muted: #64748b;
    --primary: #0f4c75; --accent: #1b9aaa; --danger: #dc2626;
    --warning: #d97706; --success: #059669; --border: #e2e8f0;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
  header {{ background: linear-gradient(135deg, var(--primary), #3282b8); color: white; padding: 2rem; border-radius: 12px; margin-bottom: 2rem; }}
  header h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  header p {{ opacity: 0.9; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
  .card {{ background: var(--card); border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--border); }}
  .card h3 {{ color: var(--primary); margin-bottom: 1rem; font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .stat-number {{ font-size: 2.5rem; font-weight: 700; color: var(--primary); }}
  .stat-label {{ color: var(--muted); font-size: 0.9rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; }}
  th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.9rem; }}
  th {{ background: #f1f5f9; color: var(--primary); font-weight: 600; }}
  tr:hover {{ background: #f8fafc; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }}
  .badge-critico {{ background: #fef2f2; color: var(--danger); }}
  .badge-alto {{ background: #fffbeb; color: var(--warning); }}
  .badge-medio {{ background: #ecfdf5; color: var(--success); }}
  .badge-baixo {{ background: #eff6ff; color: var(--primary); }}
  .insight-box {{ background: #f0f9ff; border-left: 4px solid var(--accent); padding: 1rem 1.5rem; border-radius: 0 8px 8px 0; margin-bottom: 1rem; }}
  .recommendation {{ padding: 0.5rem 0; border-bottom: 1px solid var(--border); }}
  .recommendation:last-child {{ border-bottom: none; }}
  .finops-table td:nth-child(2) {{ text-align: right; font-family: monospace; }}
  footer {{ text-align: center; color: var(--muted); padding: 2rem; font-size: 0.85rem; }}
  @media (max-width: 768px) {{ .container {{ padding: 1rem; }} .stat-number {{ font-size: 1.8rem; }} }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🛡️ FinGuard — Dashboard Executivo</h1>
    <p>Relatório gerado em {report['metadata']['gerado_em']} | {stats['total_processadas']} reclamações processadas | Grupo 14</p>
  </header>

  <div class="grid">
    <div class="card">
      <h3>Total Processadas</h3>
      <div class="stat-number">{stats['total_processadas']}</div>
      <div class="stat-label">{stats['bloqueadas']} bloqueadas | {stats['erros']} erros</div>
    </div>
    <div class="card">
      <h3>Custo Total (FinOps)</h3>
      <div class="stat-number">USD {finops['total_cost_usd']:.4f}</div>
      <div class="stat-label">{finops['total_calls']} chamadas | {finops['total_tokens']:,} tokens</div>
    </div>
    <div class="card">
      <h3>Tempo de Execução</h3>
      <div class="stat-number">{finops['elapsed_seconds']:.1f}s</div>
      <div class="stat-label">Custo/reclamação: USD {finops.get('cost_per_complaint', 0):.4f}</div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h3>Distribuição por Categoria</h3>
      <table>
        <tr><th>Categoria</th><th>Qtd</th></tr>
        {''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in stats['por_categoria'].items())}
      </table>
    </div>
    <div class="card">
      <h3>Distribuição por Urgência</h3>
      <table>
        <tr><th>Urgência</th><th>Qtd</th></tr>
        {''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in stats['por_urgencia'].items())}
      </table>
    </div>
    <div class="card">
      <h3>Distribuição por Risco</h3>
      <table>
        <tr><th>Nível</th><th>Qtd</th></tr>
        {''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in stats['por_nivel_risco'].items())}
      </table>
    </div>
  </div>

  <div class="card" style="margin-bottom: 2rem;">
    <h3>Resumo Executivo</h3>
    <div class="insight-box">{insights.get('resumo_executivo', 'N/A')}</div>
    <h3 style="margin-top: 1rem;">Tendências Identificadas</h3>
    <div class="insight-box">{insights.get('tendencias', 'N/A')}</div>
  </div>

  <div class="grid">
    <div class="card">
      <h3>⚠️ Alertas Críticos</h3>
      {''.join(f'<div class="recommendation">🔴 {a}</div>' for a in insights.get('alertas_criticos', [])) or '<p style="color:var(--muted)">Nenhum alerta crítico.</p>'}
    </div>
    <div class="card">
      <h3>📋 Recomendações</h3>
      {''.join(f'<div class="recommendation">✅ {r}</div>' for r in insights.get('recomendacoes', [])) or '<p style="color:var(--muted)">Nenhuma recomendação.</p>'}
    </div>
  </div>

  <div class="card" style="margin-bottom: 2rem;">
    <h3>🔥 Reclamações Críticas (Top 10)</h3>
    <table>
      <tr><th>ID</th><th>Categoria</th><th>Produto</th><th>Urgência</th><th>Risco</th><th>Resumo</th></tr>
      {''.join(f"""<tr>
        <td>{c.get('id','')}</td>
        <td>{c.get('categoria','')}</td>
        <td>{c.get('produto','')}</td>
        <td>{c.get('urgencia','')}</td>
        <td><span class="badge badge-{c.get('nivel_risco','').lower()}">{c.get('nivel_risco','')}</span></td>
        <td>{(c.get('resumo','') or '')[:120]}...</td>
      </tr>""" for c in stats.get('reclamacoes_criticas', [])[:10])}
    </table>
  </div>

  <div class="card" style="margin-bottom: 2rem;">
    <h3>💰 Análise FinOps Detalhada</h3>
    <table class="finops-table">
      <tr><th>Métrica</th><th>Valor</th></tr>
      <tr><td>Total de chamadas LLM</td><td>{finops['total_calls']}</td></tr>
      <tr><td>Tokens de entrada</td><td>{finops['total_prompt_tokens']:,}</td></tr>
      <tr><td>Tokens de saída</td><td>{finops['total_completion_tokens']:,}</td></tr>
      <tr><td>Total de tokens</td><td>{finops['total_tokens']:,}</td></tr>
      <tr><td>Custo total estimado</td><td>USD {finops['total_cost_usd']:.4f}</td></tr>
      <tr><td>Custo por reclamação</td><td>USD {finops.get('cost_per_complaint', 0):.4f}</td></tr>
      <tr><td>Tempo total</td><td>{finops['elapsed_seconds']:.1f}s</td></tr>
    </table>
    <h3 style="margin-top: 1rem;">Custo por Tipo de Tarefa</h3>
    <table class="finops-table">
      <tr><th>Tarefa</th><th>Chamadas</th><th>Tokens</th><th>Custo (USD)</th></tr>
      {''.join(f"<tr><td>{k}</td><td>{v['calls']}</td><td>{v['tokens']:,}</td><td>{v['cost_usd']:.4f}</td></tr>" for k, v in finops.get('by_task_type', {}).items())}
    </table>
  </div>

  <footer>
    FinGuard — Future Minds 3 | Grupo 14 | Gerado automaticamente pelo pipeline multi-agente
  </footer>
</div>
</body>
</html>"""

        output_path = config.REPORT_HTML
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"Dashboard HTML salvo em: {output_path}")
        return output_path