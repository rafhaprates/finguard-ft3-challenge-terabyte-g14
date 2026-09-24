"""
FinGuard - Gerador Automático de ADR (Architectural Decision Record)
Gera um arquivo HTML navegável, moderno e responsivo documentando
as decisões de arquitetura do projeto FinGuard.
"""

import logging
from pathlib import Path
from datetime import datetime

import config

logger = logging.getLogger(__name__)


def generate_adr(output_path: Path | None = None) -> Path:
    """Gera o ADR em HTML e salva no caminho configurado."""
    path = output_path or config.ADR_HTML
    generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADR — FinGuard (Grupo 14)</title>
<style>
    :root {{
        --bg: #f8fafc; --card: #ffffff; --text: #1e293b; --muted: #64748b;
        --primary: #0f4c75; --accent: #1b9aaa; --border: #e2e8f0;
        --success: #059669; --warning: #d97706; --danger: #dc2626;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 2rem; }}
    header {{ background: linear-gradient(135deg, var(--primary), #3282b8); color: white; padding: 2.5rem 2rem; border-radius: 12px; margin-bottom: 2rem; }}
    header h1 {{ font-size: 1.8rem; margin-bottom: 0.3rem; }}
    header .subtitle {{ opacity: 0.9; font-size: 1rem; }}
    header .meta {{ margin-top: 1rem; font-size: 0.85rem; opacity: 0.8; }}
    nav {{ background: var(--card); border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 2rem; border: 1px solid var(--border); position: sticky; top: 1rem; z-index: 10; }}
    nav a {{ color: var(--primary); text-decoration: none; margin-right: 1.2rem; font-size: 0.9rem; font-weight: 500; }}
    nav a:hover {{ color: var(--accent); text-decoration: underline; }}
    section {{ background: var(--card); border-radius: 10px; padding: 2rem; margin-bottom: 1.5rem; border: 1px solid var(--border); }}
    section h2 {{ color: var(--primary); font-size: 1.3rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid var(--accent); }}
    section h3 {{ color: var(--primary); font-size: 1.05rem; margin: 1.2rem 0 0.5rem; }}
    p {{ margin-bottom: 0.8rem; }}
    ul, ol {{ margin: 0.5rem 0 1rem 1.5rem; }}
    li {{ margin-bottom: 0.4rem; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }}
    th, td {{ padding: 0.7rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: #f1f5f9; color: var(--primary); font-weight: 600; }}
    tr:hover {{ background: #f8fafc; }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }}
    .badge-pro {{ background: #ecfdf5; color: var(--success); }}
    .badge-con {{ background: #fef2f2; color: var(--danger); }}
    .decision-box {{ background: #f0f9ff; border-left: 4px solid var(--accent); padding: 1.2rem 1.5rem; border-radius: 0 8px 8px 0; margin: 1rem 0; }}
    footer {{ text-align: center; color: var(--muted); padding: 2rem; font-size: 0.85rem; }}
    @media (max-width: 768px) {{ .container {{ padding: 1rem; }} header {{ padding: 1.5rem; }} nav {{ position: static; }} }}
</style>
</head>
<body>
<div class="container">

<header>
    <h1>🏛️ Architectural Decision Record (ADR)</h1>
    <div class="subtitle">Projeto FinGuard — Future Minds 3 | Grupo 14</div>
    <div class="meta">Status: <strong>Aceito</strong> | Data: {generated_at} | Decisor: Equipe de Arquitetura G14</div>
</header>

<nav>
    <a href="#contexto">Contexto</a>
    <a href="#opcoes">Opções Comparadas</a>
    <a href="#decisao">Decisão</a>
    <a href="#tradeoffs">Trade-offs</a>
    <a href="#finops">FinOps</a>
    <a href="#seguranca">Segurança</a>
</nav>

<section id="contexto">
    <h2>1. Contexto do Problema</h2>
    <p>Instituições financeiras recebem diariamente milhares de reclamações por múltiplos canais (SAC, Ouvidoria, Banco Central, Redes Sociais). Essas mensagens chegam em texto livre, sem padronização, com linguagem informal, erros de digitação e diferentes níveis de urgência.</p>
    <p>O processo manual atual é lento, inconsistente entre analistas e propenso a erros, especialmente em picos de volume. Reclamações com indícios de fraude ou violação regulatória precisam ser escaladas rapidamente para compliance, mas frequentemente ficam presas em filas genéricas.</p>
    <h3>Desafios Específicos</h3>
    <ul>
        <li><strong>Volume:</strong> ~500 reclamações/dia com variação sazonal significativa</li>
        <li><strong>Heterogeneidade:</strong> Textos variam de formais a extremamente informais, com profanidades e dados sensíveis misturados</li>
        <li><strong>Criticidade:</strong> Necessidade de identificar rapidamente fraudes, menções a órgãos reguladores e vulnerabilidade emocional</li>
        <li><strong>Conformidade:</strong> LGPD exige que dados pessoais nunca apareçam em relatórios gerenciais</li>
        <li><strong>Custo:</strong> Processamento via LLM tem custo direto por token; uso indiscriminado de modelos grandes inviabiliza economicamente</li>
    </ul>
</section>

<section id="opcoes">
    <h2>2. Opções de Arquitetura Comparadas</h2>

    <h3>Opção A: Monolítico com Prompt Único</h3>
    <p>Uma única chamada LLM recebe o texto bruto e retorna todos os campos (categoria, produto, sentimento, urgência, resumo, risco, recomendações) em uma resposta JSON.</p>
    <table>
        <tr><th>Aspecto</th><th>Avaliação</th></tr>
        <tr><td>Complexidade</td><td><span class="badge badge-pro">Baixa</span> — Um único prompt, sem orquestração</td></tr>
        <tr><td>Custo por reclamação</td><td><span class="badge badge-con">Alto</span> — Modelo grande necessário para todas as tarefas simultaneamente</td></tr>
        <tr><td>Manutenibilidade</td><td><span class="badge badge-con">Baixa</span> — Alterar uma etapa exige reescrever todo o prompt</td></tr>
        <tr><td>Rastreabilidade</td><td><span class="badge badge-con">Baixa</span> — Logs monolíticos, difícil isolar falhas</td></tr>
        <tr><td>Escalabilidade</td><td><span class="badge badge-con">Limitada</span> — Não permite paralelismo granular</td></tr>
        <tr><td>Guardrails</td><td><span class="badge badge-con">Fraco</span> — Validação apenas pré/pós chamada única</td></tr>
    </table>

    <h3>Opção B: Multi-Agente Orquestrado com RAG + FinOps + Dual Provider (ESCOLHIDA)</h3>
    <p>Pipeline sequencial com três agentes especializados (Triagem → Risco → Relatório), motor RAG para política interna, guardrails de entrada/saída, rastreamento de custos em tempo real e suporte a dois provedores de LLM: Zup AI Gateway (Claude Haiku/Sonnet via Bedrock) e Ollama local (modelos open-source, custo zero).</p>
    <table>
        <tr><th>Aspecto</th><th>Avaliação</th></tr>
        <tr><td>Complexidade</td><td><span class="badge badge-con">Média-Alta</span> — Múltiplos componentes, orquestração necessária</td></tr>
        <tr><td>Custo por reclamação</td><td><span class="badge badge-pro">Otimizado</span> — Model Routing: leve para triagem, robusto apenas para risco</td></tr>
        <tr><td>Manutenibilidade</td><td><span class="badge badge-pro">Alta</span> — Cada agente evolui independentemente</td></tr>
        <tr><td>Rastreabilidade</td><td><span class="badge badge-pro">Completa</span> — Logs por agente, timestamps, latência, tokens</td></tr>
        <tr><td>Escalabilidade</td><td><span class="badge badge-pro">Alta</span> — Paralelismo possível entre reclamações independentes</td></tr>
        <tr><td>Guardrails</td><td><span class="badge badge-pro">Robusto</span> — Entrada e saída validadas em cada etapa</td></tr>
    </table>

    <h3>Opção C: Framework LangGraph Completo</h3>
    <p>Implementação usando LangGraph com grafo condicional, loops de validação e estado compartilhado.</p>
    <table>
        <tr><th>Aspecto</th><th>Avaliação</th></tr>
        <tr><td>Complexidade</td><td><span class="badge badge-con">Alta</span> — Curva de aprendizado do framework, dependência externa pesada</td></tr>
        <tr><td>Flexibilidade</td><td><span class="badge badge-pro">Máxima</span> — Grafos condicionais, paralelismo nativo</td></tr>
        <tr><td>Overhead</td><td><span class="badge badge-con">Significativo</span> — Para 3 etapas lineares, o framework adiciona complexidade desnecessária</td></tr>
        <tr><td>Portabilidade</td><td><span class="badge badge-con">Baixa</span> — Vendor lock-in ao ecossistema LangChain</td></tr>
    </table>
</section>

<section id="decisao">
    <h2>3. Decisão Final &amp; Justificativa</h2>
    <div class="decision-box">
        <strong>Decisão:</strong> Adotar a <strong>Opção B — Multi-Agente Orquestrado com RAG + FinOps</strong>, implementado em Python puro com biblioteca <code>openai</code> conectada a endpoint compatível (AI Gateway / LiteLLM proxy).
    </div>
    <h3>Justificativas Técnicas</h3>
    <ol>
        <li><strong>Separação de Responsabilidades:</strong> Cada agente tem um propósito claro e prompts otimizados para sua tarefa específica, melhorando a qualidade das respostas.</li>
        <li><strong>Model Routing (FinOps):</strong> Triagem usa Claude Haiku 4.5 (~$0.80/M input) enquanto análise de risco usa Claude Sonnet 4.5 (~$3.00/M input). Economia estimada de ~70% vs. usar Sonnet para tudo.</li>
        <li><strong>RAG Sem Vector DB:</strong> A política interna tem apenas 3 páginas. Busca por palavras-chave com segmentação por seções é suficiente, evitando a complexidade de embeddings e vector stores para este escopo.</li>
        <li><strong>Independência de Framework:</strong> Python puro com <code>openai</code> SDK elimina dependências pesadas (LangChain/LangGraph), reduz superfície de ataque e facilita auditoria de segurança.</li>
        <li><strong>Observabilidade Nativa:</strong> Logs estruturados com timestamps, latência e contagem de tokens em cada etapa permitem debugging e otimização contínua.</li>
        <li><strong>Compatibilidade com Restrições:</strong> Funciona com qualquer endpoint OpenAI-compatible (LiteLLM proxy, AI Gateway), atendendo à restrição de não usar AWS Bedrock diretamente.</li>
    </ol>
</section>

<section id="tradeoffs">
    <h2>4. Consequências &amp; Trade-offs</h2>
    <h3>✅ Benefícios</h3>
    <ul>
        <li>Custo operacional reduzido via roteamento inteligente de modelos</li>
        <li>Cada agente pode ser testado, versionado e melhorado isoladamente</li>
        <li>Logs granulares facilitam identificação de gargalos e falhas</li>
        <li>Guardrails em múltiplas camadas garantem conformidade com LGPD</li>
        <li>Dashboard HTML e ADR gerados automaticamente como artefatos do pipeline</li>
        <li>Arquitetura portável entre provedores (OpenAI, Azure, LiteLLM, Ollama)</li>
    </ul>
    <h3>⚠️ Riscos e Mitigações</h3>
    <table>
        <tr><th>Risco</th><th>Impacto</th><th>Mitigação</th></tr>
        <tr><td>Latência acumulada (3 chamadas LLM sequenciais)</td><td>Médio</td><td>Modelo leve na triagem reduz latência total; paralelismo entre reclamações independentes</td></tr>
        <tr><td>JSON parsing falho do LLM</td><td>Alto</td><td>Tratamento de erro com fallback; prompts com instrução explícita de formato; limpeza de markdown fences</td></tr>
        <tr><td>RAG por keyword limitado</td><td>Baixo</td><td>Política tem apenas 3 páginas; busca por seção cobre todos os casos relevantes</td></tr>
        <tr><td>Dependência de endpoint externo</td><td>Médio</td><td>Suporte dual-provider (Zup AI Gateway + Ollama local) permite alternar entre cloud e local alterando apenas LLM_PROVIDER</td></tr>
        <tr><td>Profanidade em textos de entrada</td><td>Baixo</td><td>Tolerada na entrada (cliente irritado é legítimo); ofuscada obrigatoriamente na saída</td></tr>
    </table>
</section>

<section id="finops">
    <h2>5. Análise FinOps &amp; Custos</h2>
    <h3>Estratégia de Model Routing</h3>
    <p>O sistema utiliza dois tiers de modelos para otimizar custo sem sacrificar qualidade nas etapas críticas:</p>
    <table>
        <tr><th>Tarefa</th><th>Modelo</th><th>Tier</th><th>Input ($/1M)</th><th>Output ($/1M)</th><th>Justificativa</th></tr>
        <tr><td>Triagem / Classificação</td><td>Claude Haiku 4.5</td><td>Leve</td><td>$0.80</td><td>$4.00</td><td>Tarefa de extração estruturada; não requer raciocínio complexo</td></tr>
        <tr><td>Análise de Risco</td><td>Claude Sonnet 4.5</td><td>Robusto</td><td>$3.00</td><td>$15.00</td><td>Requer cruzamento de política interna, avaliação jurídica e regulatória</td></tr>
        <tr><td>Relatório Gerencial</td><td>Claude Sonnet 4.5</td><td>Robusto</td><td>$3.00</td><td>$15.00</td><td>Síntese executiva com recomendações acionáveis</td></tr>
    </table>

    <h3>Estimativa de Custo por Lote (500 reclamações)</h3>
    <table>
        <tr><th>Componente</th><th>Tokens Estimados</th><th>Custo Estimado (USD)</th></tr>
        <tr><td>Triagem (500 × Claude Haiku 4.5)</td><td>~750K input + ~125K output</td><td>~$1.10</td></tr>
        <tr><td>Risco (500 × Claude Sonnet 4.5)</td><td>~1.5M input + ~250K output</td><td>~$8.25</td></tr>
        <tr><td>Relatório (1 × Claude Sonnet 4.5)</td><td>~10K input + ~1K output</td><td>~$0.05</td></tr>
        <tr><td><strong>Total estimado</strong></td><td><strong>~2.6M tokens</strong></td><td><strong>~$9.40</strong></td></tr>
    </table>
    <p>💡 O budget disponível (BUDGET_FT) é de <strong>USD 6.54</strong>. Para processar dentro do budget, utilize <code>--sample</code> (10 reclamações) ou <code>--limit 300</code>.</p>

    <h3>Comparativo: Sem Model Routing</h3>
    <p>Se todas as etapas usassem Claude Sonnet 4.5 (modelo robusto):</p>
    <table>
        <tr><th>Cenário</th><th>Custo Total (500 rec.)</th><th>Diferença</th></tr>
        <tr><td>Com Model Routing (Haiku+Sonnet)</td><td>~$9.40</td><td>—</td></tr>
        <tr><td>Sem routing (tudo Sonnet)</td><td>~$33.75</td><td>+259%</td></tr>
        <tr><td><strong>Economia</strong></td><td><strong>~$24.35</strong></td><td><strong>-72%</strong></td></tr>
    </table>
    <p>A economia de ~72% justifica a complexidade adicional do roteamento inteligente. Em escala de produção (milhares de reclamações/dia), essa diferença representa milhares de dólares mensais.</p>

    <h3>Cenário Alternativo: Ollama Local (Custo Zero)</h3>
    <p>O sistema suporta alternância para modelos locais via variável <code>LLM_PROVIDER=ollama</code>, eliminando completamente o custo operacional:</p>
    <table>
        <tr><th>Provider</th><th>Modelo Triagem</th><th>Modelo Risco</th><th>Custo 500 rec.</th><th>Observação</th></tr>
        <tr><td>Zup AI Gateway</td><td>Claude Haiku 4.5</td><td>Claude Sonnet 4.5</td><td>~$9.40</td><td>Maior qualidade, requer budget</td></tr>
        <tr><td>Ollama Local</td><td>qwen2.5:7b</td><td>qwen2.5:14b</td><td>$0.00</td><td>Custo zero, qualidade dependente do modelo local</td></tr>
    </table>
    <p>A arquitetura dual-provider permite desenvolvimento e testes locais sem custo, com deploy em produção usando modelos cloud de maior capacidade quando necessário.</p>
</section>

<section id="seguranca">
    <h2>6. Recomendações de Segurança</h2>

    <h3>Guardrails de Entrada (Input)</h3>
    <ul>
        <li><strong>Detecção de Prompt Injection:</strong> Padrões regex identificam tentativas de ignorar instruções, extrair system prompt, jailbreak (DAN), e tags especiais de modelos (&lt;|im_start|&gt;, [INST], etc.)</li>
        <li><strong>Validação de Escopo:</strong> Entradas vazias ou fora do contexto bancário são bloqueadas antes de chegar ao LLM</li>
        <li><strong>Resposta Educada:</strong> Bloqueios retornam mensagem profissional em português, sem expor detalhes internos do sistema</li>
        <li><strong>Tolerância a Profanidade:</strong> Linguagem imprópria na entrada é tolerada (cliente insatisfeito é legítimo), mas será ofuscada na saída</li>
    </ul>

    <h3>Guardrails de Saída (Output)</h3>
    <ul>
        <li><strong>PII Masking Automático:</strong> CPF, números de cartão, conta bancária, e-mail e telefone são ofuscados via regex antes de qualquer exibição</li>
        <li><strong>Filtro de Profanidade:</strong> Termos impróprios são substituídos por <code>[TERMO_OFUSCADO]</code> em todas as saídas</li>
        <li><strong>Sanitização em Múltiplas Camadas:</strong> Resumo da triagem, justificativa de risco e relatório final passam por sanitização independente</li>
    </ul>

    <h3>Conformidade LGPD</h3>
    <ul>
        <li>Nenhum dado pessoal aparece em relatórios gerenciais ou logs</li>
        <li>Dados sintéticos exclusivamente — proibido uso de dados reais</li>
        <li>Logs contêm apenas IDs de reclamação e métricas operacionais</li>
        <li>Arquivos de resultado podem ser deletados após apresentação sem perda de rastreabilidade</li>
    </ul>

    <h3>Recomendações para Produção</h3>
    <ul>
        <li>Implementar rate limiting no endpoint do proxy LLM</li>
        <li>Adicionar autenticação mútua (mTLS) entre serviços</li>
        <li>Criptografar logs em repouso e em trânsito</li>
        <li>Implementar audit trail imutável para decisões de compliance</li>
        <li>Realizar testes adversariais periódicos nos guardrails</li>
        <li>Monitorar drift de distribuição nas classificações dos agentes</li>
    </ul>
</section>

<footer>
    FinGuard — Future Minds 3 | Grupo 14 | ADR gerado automaticamente pelo pipeline<br>
    Este documento reflete as decisões arquiteturais tomadas durante o desenvolvimento da solução.
</footer>

</div>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")
    logger.info(f"ADR HTML salvo em: {path}")
    return path