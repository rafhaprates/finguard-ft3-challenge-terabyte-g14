# 🛡️ FinGuard — Assistente Inteligente de Análise de Reclamações de Clientes

**Future Minds 3 | Nível 3 — O Arquiteto (Categoria Terabyte) | Grupo 14**

> Sistema multi-agente orquestrado para triagem inteligente, análise de risco, governança, segurança e rastreabilidade de custos (FinOps) em reclamações bancárias.

---

## 👤 Autor

**Rafhael Prates Parra Cieto**
📧 rafhael.cieto@zup.com.br

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Decisões Técnicas](#decisões-técnicas)
4. [Estrutura do Projeto](#estrutura-do-projeto)
5. [Pré-requisitos](#pré-requisitos)
6. [Instalação Passo a Passo](#instalação-passo-a-passo)
7. [Configuração](#configuração)
8. [Execução](#execução)
9. [Artefatos Gerados](#artefatos-gerados)
10. [Módulos Detalhados](#módulos-detalhados)
11. [Segurança e Guardrails](#segurança-e-guardrails)
12. [FinOps e Model Routing](#finops-e-model-routing)
13. [Limitações e Trabalhos Futuros](#limitações-e-trabalhos-futuros)

---

## Visão Geral

O **FinGuard** é uma solução completa para automação da análise de reclamações de clientes em instituições financeiras. O sistema recebe reclamações em texto livre (de SAC, Ouvidoria, Banco Central, Redes Sociais) e executa um pipeline multi-agente que:

1. **Triagem** — Classifica categoria, produto, sentimento, urgência e gera resumo padronizado
2. **Análise de Risco** — Cruza dados com a Política Interna via RAG, avalia risco financeiro/jurídico/reputacional e determina SLA
3. **Relatório Gerencial** — Compila estatísticas, gera insights executivos e produz dashboard HTML interativo

Tudo isso com **guardrails de entrada/saída**, **sanitização automática de PII**, **rastreamento de custos em tempo real** e **documentação arquitetural automática (ADR)**.

### Dataset

O projeto utiliza exclusivamente dados sintéticos fornecidos pelo desafio:
- **Reclamações:** `artifacts/dataset_finguard_desafio_3 (4).csv` (~500 registros)
- **Política Interna:** `artifacts/KS_POLITICA_INTERNA (4).pdf` (3 páginas)

Nenhum dado real ou sensível é utilizado.

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    main.py (Entry Point)                 │
│         Carrega CSV → Orquestra → Gera Artefatos        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              orchestrator.py (Coordenação)               │
│   Logs estruturados · Timeline · Status por agente      │
└──────┬──────────────────┬──────────────────┬────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐   ┌──────────────┐   ┌─────────────────┐
│  Triagem    │   │   Risco      │   │   Relatório     │
│  Agent      │──▶│   Agent      │──▶│   Agent         │
│(Haiku 4.5)  │   │(Sonnet 4.5)  │   │ (Sonnet 4.5)    │
└──────┬──────┘   └──────┬───────┘   └────────┬────────┘
       │                 │                     │
       ▼                 ▼                     ▼
┌─────────────┐   ┌──────────────┐      ┌────────────┐
│ Guardrails  │   │  RAG Engine  │      │  Dashboard │
│ Input/Output│   │ (Policy PDF) │      │    HTML    │
└─────────────┘   └──────────────┘      └────────────┘
       │                                       │
       ▼                                       ▼
┌─────────────────────────────────────────────────────────┐
│                  finops.py (Custos)                      │
│   Token counting · Model Routing · Cost estimation      │
└─────────────────────────────────────────────────────────┘
```

### Fluxo por Reclamação

```
Texto Bruto → Input Guardrail → Triagem (LLM leve) → Output Sanitization
     → RAG Query (Política) → Análise Risco (LLM robusto) → Output Sanitization
     → Acumulação → Relatório Gerencial (LLM robusto) → Dashboard HTML
```

---

## Decisões Técnicas

### 1. Multi-Agente vs. Monolítico

**Decisão:** Pipeline sequencial com 3 agentes especializados.

| Critério | Monolítico | Multi-Agente (escolhido) |
|----------|-----------|------------------------|
| Custo por reclamação | Alto (Sonnet 4.5 para tudo) | Otimizado (Haiku 4.5 triagem + Sonnet 4.5 risco) |
| Manutenibilidade | Baixa (prompt único gigante) | Alta (cada agente evolui isoladamente) |
| Rastreabilidade | Logs monolíticos | Logs granulares por etapa |
| Guardrails | Validação pré/pós única | Validação em cada camada |
| Economia estimada | — | **~72% vs. Sonnet único** |

### 2. OpenAI SDK vs. LangChain/LangGraph

**Decisão:** Python puro com `openai` SDK conectado ao AI Gateway Zup (LiteLLM proxy).

- Elimina dependências pesadas (~200MB+ do LangChain ecossystem)
- Reduz superfície de ataque e facilita auditoria de segurança
- Conecta-se ao AI Gateway Zup via `DefaultHttpxClient(verify=False)` (sandbox)
- Roteia automaticamente para Claude Haiku 4.5 ou Sonnet 4.5 via Bedrock
- Para 3 etapas lineares, frameworks de orquestração adicionam complexidade sem benefício proporcional

### 3. RAG por Keyword vs. Vector DB

**Decisão:** Busca por palavras-chave com segmentação por seções numeradas.

- A política interna tem apenas 3 páginas — embeddings + vector store seria over-engineering
- Segmentação automática por seções numeradas (2.1, 3.4, etc.) cobre todos os casos relevantes
- Zero dependência externa (sem ChromaDB, Pinecone, FAISS)
- Latência de consulta < 1ms vs. ~50-200ms de vector search

### 4. Model Routing (FinOps)

**Decisão:** Dois tiers de modelos roteados por tipo de tarefa.

| Tarefa | Modelo | Tier | Justificativa |
|--------|--------|------|---------------|
| Triagem | Claude Haiku 4.5 | Leve ($0.80/M input) | Extração estruturada simples |
| Risco | Claude Sonnet 4.5 | Robusto ($3.00/M input) | Cruzamento regulatório complexo |
| Relatório | Claude Sonnet 4.5 | Robusto ($3.00/M input) | Síntese executiva acionável |

Economia estimada de **~70%** comparado ao uso exclusivo de modelo robusto.

### 5. Guardrails Regex vs. LLM-as-Judge

**Decisão:** Regex determinístico para PII e injection detection.

- Latência zero (vs. chamada LLM adicional de ~500ms)
- Custo zero (vs. tokens extras por validação)
- Determinístico e auditável (vs. probabilidade do LLM)
- Suficiente para padrões conhecidos de PII brasileiro e prompt injection

### 6. HTML Estático vs. Framework Web

**Decisão:** Dashboards e ADR em HTML/CSS puro inline.

- Zero dependência de servidor web ou build tools
- Portável como arquivo único (abre em qualquer browser)
- Responsivo e estilizado com CSS variables
- Adequado para entrega em challenge/pitch

---

## Estrutura do Projeto

```
zup-fm3-g14-finguard/
├── .gitignore
├── README.md
├── artifacts/
│   ├── dataset_finguard_desafio_3 (4).csv   # Dataset sintético de reclamações
│   ├── KS_POLITICA_INTERNA (4).pdf          # Política interna para RAG
│   ├── document.md                          # Especificação do desafio
│   └── ft3.pdf                              # Documento complementar
└── finguard_project/
    ├── .env.example          # Template de variáveis de ambiente
    ├── config.py             # Configurações globais e carregamento de env
    ├── guardrails.py         # Input/Output guardrails e PII masking
    ├── rag_engine.py         # Motor RAG para política interna
    ├── finops.py             # Token counting, cost tracking, model routing
    ├── orchestrator.py       # Coordenação multi-agente e logging
    ├── adr_generator.py      # Gerador automático de ADR em HTML
    ├── main.py               # Entry point e CLI
    ├── agents/
    │   ├── __init__.py
    │   ├── triagem_agent.py      # Agente 1: classificação e extração
    │   ├── risco_agent.py        # Agente 2: risco e compliance
    │   └── relatorio_agent.py    # Agente 3: relatório e dashboard
    └── output/               # Gerado em runtime (gitignored)
        ├── resultados_analise.json
        ├── relatorio_executivo.html
        ├── adr.html
        ├── finops_report.json
        └── finguard_execution.log
```

---

## Pré-requisitos

- **Python 3.10+**
- **Um dos seguintes provedores de LLM:**
  - **Zup AI Gateway (default)** — endpoint sandbox da Zup com token `KEY_FT` (Claude Haiku/Sonnet via Bedrock)
  - **Ollama Local** — modelos open-source rodando localmente, custo zero, sem dependência externa
- **Variáveis de ambiente no `~/.zshrc`** (para Zup) ou **Ollama instalado** (para local)
- **Sistema operacional:** macOS, Linux ou Windows (WSL recomendado)

> ⚠️ No modo Zup, o projeto utiliza `DefaultHttpxClient(verify=False)` pois o AI Gateway roda em sandbox com certificado autoassinado. No modo Ollama, SSL verification está habilitado automaticamente. **Nunca use `verify=False` em produção.**

---

## Instalação Passo a Passo

### 1. Clone o repositório

```bash
git clone <repo-url>
cd zup-fm3-g14-finguard
```

### 2. Crie o ambiente virtual

```bash
python3 -m venv finguard_env
source finguard_env/bin/activate        # macOS/Linux
# ou: finguard_env\Scripts\activate     # Windows
```

### 3. Instale as dependências

```bash
pip install --upgrade pip
pip install pandas plotly matplotlib scikit-learn openai litellm pypdf python-dotenv pydantic
```

### 4. Verifique as variáveis de ambiente

As credenciais do AI Gateway Zup já devem estar configuradas no seu `~/.zshrc`:

```bash
# Verifique se as variáveis estão disponíveis
echo $KEY_FT
echo $LITELLM_PROXY_URL
echo $MODEL_HAIKU_FT
echo $MODEL_SONNET_FT
echo $BUDGET_FT
```

Se alguma variável estiver vazia, adicione ao `~/.zshrc`:

```bash
export KEY_FT="seu-token-aqui"
export LITELLM_PROXY_URL="https://dx-ai-gateway.platform.sbox.zupcloud.corp"
export MODEL_HAIKU_FT="bedrock-anthropic-claude-haiku-4-5"
export MODEL_SONNET_FT="bedrock-anthropic-claude-sonnet-4-5"
export BUDGET_FT="6.54"
```

Depois recarregue o shell: `source ~/.zshrc`

> ⚠️ O arquivo `.env` é opcional e serve apenas como fallback para custos e logging. As credenciais principais vêm do shell. Nunca commite `.env`.

---

## Configuração

### Seleção de Provider

O FinGuard suporta dois provedores de LLM, selecionados pela variável `LLM_PROVIDER`:

| Provider | Valor | Descrição |
|----------|-------|-----------|
| **Zup AI Gateway** | `zup` (default) | Claude Haiku/Sonnet via Bedrock, endpoint sandbox Zup |
| **Ollama Local** | `ollama` | Modelos open-source locais, custo zero, sem dependência externa |

Para trocar de provider, defina no shell ou no `.env`:
```bash
export LLM_PROVIDER=zup    # ou "ollama"
```

### Provider: Zup AI Gateway (default)

As credenciais são carregadas diretamente das variáveis de ambiente do shell (`~/.zshrc`). Não é necessário criar `.env` manualmente — o sistema lê do ambiente automaticamente.

| Variável | Descrição | Valor Atual |
|----------|-----------|-------------|
| `KEY_FT` | Token de autenticação do AI Gateway (LiteLLM proxy) | *(definido no ~/.zshrc)* |
| `LITELLM_PROXY_URL` | Endpoint do AI Gateway Zup | `https://dx-ai-gateway.platform.sbox.zupcloud.corp` |
| `KEY_ALIAS_FT` | Alias identificador da chave | `future-minds-005` |
| `BUDGET_FT` | Budget disponível em USD para o desafio | `6.54` |
| `MODEL_HAIKU_FT` | Modelo leve para triagem (Claude Haiku via Bedrock) | `bedrock-anthropic-claude-haiku-4-5` |
| `MODEL_SONNET_FT` | Modelo robusto para risco/relatório (Claude Sonnet via Bedrock) | `bedrock-anthropic-claude-sonnet-4-5` |

#### Conexão com AI Gateway (Sandbox)

O projeto utiliza `DefaultHttpxClient(verify=config.VERIFY_SSL)` na inicialização do cliente OpenAI. No modo Zup, `VERIFY_SSL=False` pois o gateway usa certificado autoassinado. No modo Ollama, `VERIFY_SSL=True` automaticamente.

```python
from openai import OpenAI, DefaultHttpxClient
import config

client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_BASE_URL,
    http_client=DefaultHttpxClient(verify=config.VERIFY_SSL),
)
```

> ⚠️ **Nunca use `verify=False` em produção.** Em ambiente produtivo, configure o certificado CA correto.

### Provider: Ollama Local

Para usar modelos locais sem custo e sem dependência externa:

1. **Instale o Ollama:** [https://ollama.com](https://ollama.com)
2. **Baixe os modelos recomendados:**
   ```bash
   ollama pull qwen2.5:7b    # Modelo leve para triagem
   ollama pull qwen2.5:14b   # Modelo robusto para risco/relatório
   ```
3. **Configure o provider:**
   ```bash
   export LLM_PROVIDER=ollama
   # Opcionais (defaults já configurados):
   export OLLAMA_BASE_URL=http://localhost:11434/v1
   export OLLAMA_MODEL_LIGHT=qwen2.5:7b
   export OLLAMA_MODEL_HEAVY=qwen2.5:14b
   ```
4. **Verifique se o Ollama está rodando:**
   ```bash
   curl http://localhost:11434/v1/models
   ```

> 💡 No modo Ollama, os custos no FinOps são zerados automaticamente (`COST_*=0.00`) pois a infraestrutura é local.

### Variáveis Opcionais (`.env` como fallback)

| Variável | Descrição | Default (Zup) | Default (Ollama) |
|----------|-----------|---------------|------------------|
| `LLM_PROVIDER` | Provedor ativo | `zup` | — |
| `COST_INPUT_LIGHT` | Custo input modelo leve ($/1M tokens) | `0.80` | `0.00` |
| `COST_OUTPUT_LIGHT` | Custo output modelo leve ($/1M tokens) | `4.00` | `0.00` |
| `COST_INPUT_HEAVY` | Custo input modelo robusto ($/1M tokens) | `3.00` | `0.00` |
| `COST_OUTPUT_HEAVY` | Custo output modelo robusto ($/1M tokens) | `15.00` | `0.00` |
| `LOG_LEVEL` | Nível de logging | `INFO` | `INFO` |

### Model Routing

O roteamento é automático baseado no provider e nas variáveis configuradas:

| Tarefa | Zup (default) | Ollama |
|--------|---------------|--------|
| **Triagem** | Claude Haiku 4.5 (leve) | qwen2.5:7b (leve) |
| **Risco** | Claude Sonnet 4.5 (robusto) | qwen2.5:14b (robusto) |
| **Relatório** | Claude Sonnet 4.5 (robusto) | qwen2.5:14b (robusto) |

O FinOps tracker classifica modelos como "leves" ou "pesados" baseado em indicadores no nome (`haiku`, `mini`, `flash`, `nano`, `qwen2.5:7b` = leve; demais = pesado).

---

## Execução

### Processar amostra rápida (10 reclamações)

```bash
cd finguard_project
python main.py --sample
```

### Processar lote limitado

```bash
python main.py --limit 50
```

### Processar dataset completo (~500 reclamações)

```bash
python main.py
```

### Saída esperada no console

```
============================================================
🛡️ FinGuard — Resumo da Execução
============================================================
  Reclamações processadas: 500
  Bloqueadas por guardrail: 0
  Erros: 0
  Tempo total: 342.5s
  Custo estimado: USD 6.4821
  Tokens consumidos: 2,614,320
  Chamadas LLM: 1001
------------------------------------------------------------
  📁 Artefatos gerados:
  Resultados JSON: output/resultados_analise.json
  Dashboard HTML: output/relatorio_executivo.html
  Relatório FinOps:output/finops_report.json
  ADR HTML: output/adr.html
  Logs: output/finguard_execution.log
============================================================
```

---

## Artefatos Gerados

Todos os artefatos são salvos em `finguard_project/output/`:

| Arquivo | Descrição |
|---------|-----------|
| `resultados_analise.json` | Análise individual de cada reclamação (triagem + risco) |
| `relatorio_executivo.html` | Dashboard interativo com estatísticas, gráficos e insights |
| `adr.html` | Architectural Decision Record navegável e responsivo |
| `finops_report.json` | Detalhamento de tokens, custos e latência por chamada |
| `finguard_execution.log` | Log completo da execução com timestamps e status |

---

## Módulos Detalhados

### `config.py`
Carrega credenciais do AI Gateway Zup (`KEY_FT`, `LITELLM_PROXY_URL`) e modelos (`MODEL_HAIKU_FT`, `MODEL_SONNET_FT`) diretamente das variáveis de ambiente do shell (`~/.zshrc`). Usa `python-dotenv` como fallback opcional. Define caminhos absolutos para artefatos e expõe constantes de custo e logging para todo o projeto. A API key não é obrigatória em tempo de import, permitindo geração de ADR e testes de módulo sem credenciais configuradas.

### `guardrails.py`
Implementa duas camadas de segurança:
- **Input Guardrails:** Detecta prompt injection (10 padrões regex), jailbreak attempts, tags especiais de modelos e entradas vazias
- **Output Guardrails:** Ofusca CPF (`***.***.***-**`), cartão de crédito (`****-****-****-****`), conta bancária, e-mail, telefone e substitui termos impróprios por `[TERMO_OFUSCADO]`

### `rag_engine.py`
Motor de RAG leve que extrai texto do PDF da política interna, segmenta em seções numeradas e realiza busca por palavras-chave com scoring de relevância. Cache LRU de 64 entradas evita reprocessamento. Método `get_sla_info()` combina urgência + produto para retornar trechos específicos de SLA.

### `agents/triagem_agent.py`
Agente 1 do pipeline. Recebe texto bruto, aplica input guardrail, chama LLM leve com prompt estruturado para extração de categoria/produto/sentimento/urgência/resumo, sanitiza a saída e registra métricas no FinOps tracker. Retorna dict padronizado ou marca como bloqueado/erro.

### `agents/risco_agent.py`
Agente 2 do pipeline. Consulta o RAG com base na urgência e produto da triagem, monta prompt contextualizado com trechos da política, chama LLM robusto para avaliação de risco/compliance, sanitiza justificativas e determina necessidade de escalonamento.

### `agents/relatorio_agent.py`
Agente 3 do pipeline. Compila estatísticas agregadas (distribuição por categoria, urgência, risco, produto), chama LLM para gerar insights executivos e recomendações, e produz dashboard HTML completo com CSS inline responsivo.

### `orchestrator.py`
Coordena o fluxo sequencial Triagem → Risco → Relatório para cada reclamação. Configura logging dual (arquivo + console), gerencia instâncias dos agentes e do RAG, salva resultados individuais e relatório FinOps ao final do lote.

### `finops.py`
Rastreia tokens e custos em tempo real. Classifica modelos como leves/pesados por nome, calcula custo por chamada usando taxas configuráveis, fornece método `get_routing_model()` para seleção automática de modelo por tarefa e gera relatório detalhado em JSON.

### `adr_generator.py`
Gera automaticamente o Architectural Decision Record em HTML com navegação sticky, comparação de 3 opções arquiteturais, justificativa técnica, tabela de trade-offs, análise FinOps comparativa e recomendações de segurança. Totalmente auto-contido (CSS inline, sem dependências externas).

### `main.py`
Entry point com CLI via argparse. Carrega dataset CSV (com suporte a BOM do Excel), suporta flags `--sample` (10 registros) e `--limit N`, inicializa o orquestrador, processa o lote, gera ADR e imprime resumo executivo no console.

---

## Segurança e Guardrails

### Input Guardrails

| Ameaça | Detecção | Ação |
|--------|----------|------|
| Prompt Injection | 10 padrões regex (ignore previous, DAN, system prompt extraction, etc.) | Bloqueio com mensagem educada |
| Jailbreak | Tags especiais (`<\|im_start\|>`, `[INST]`, `<<SYS>>`) | Bloqueio |
| Entrada vazia | Validação de string | Bloqueio |
| Profanidade | Tolerada na entrada (cliente irritado é legítimo) | Ofuscada apenas na saída |

### Output Guardrails (PII Masking)

| Tipo de Dado | Padrão | Máscara |
|-------------|--------|---------|
| CPF | `\d{3}\.\d{3}\.\d{3}-\d{2}` ou `\d{11}` | `***.***.***-**` |
| Cartão de Crédito | `(?:\d{4}[- ]?){3}\d{4}` | `****-****-****-****` |
| Conta Bancária | Contexto + dígitos | `[CONTA_OFUSCADA]` |
| E-mail | RFC 5322 simplificado | `[EMAIL_OFUSCADO]` |
| Telefone BR | `(XX) XXXXX-XXXX` | `[TELEFONE_OFUSCADO]` |
| Termos Impróprios | Lista de ~25 termos PT-BR | `[TERMO_OFUSCADO]` |

### Conformidade LGPD

- Nenhum dado pessoal em relatórios gerenciais ou logs
- Dados exclusivamente sintéticos
- Logs contêm apenas IDs e métricas operacionais
- Arquivos de resultado podem ser deletados sem perda de rastreabilidade

---

## FinOps e Model Routing

### Estratégia

O sistema implementa **roteamento inteligente de modelos** onde tarefas simples usam modelos leves e baratos, reservando modelos robustos (e caros) apenas para análises complexas.

### Estimativa de Custo (500 reclamações)

| Componente | Tokens | Custo (USD) |
|-----------|--------|-------------|
| Triagem (Claude Haiku 4.5) | ~875K | ~$1.20 |
| Risco (Claude Sonnet 4.5) | ~1.75M | ~$9.00 |
| Relatório (Claude Sonnet 4.5) | ~11K | ~$0.05 |
| **Total** | **~2.6M** | **~$10.25** |

> 💡 O budget disponível (`BUDGET_FT`) é de **USD 6.54**. Para processar o dataset completo dentro do budget, utilize `--sample` (10 reclamações) ou `--limit 300`.

### Comparativo

| Cenário | Custo (500 rec.) | Diferença |
|---------|-----------------|-----------|
| Com Model Routing (Haiku+Sonnet) | ~$10.25 | Baseline |
| Sem routing (tudo Sonnet) | ~$33.75 | +229% |
| **Economia** | **~$23.50** | **-70%** |

---

## Limitações e Trabalhos Futuros

### Limitações Atuais

- **RAG por keyword:** Adequado para 3 páginas, mas não escala para documentos extensos sem vector DB
- **Pipeline sequencial:** Reclamações são processadas uma a uma; paralelismo entre reclamações independentes não implementado
- **Guardrails regex:** Cobre padrões conhecidos, mas não detecta variações criativas de prompt injection
- **Sem persistência:** Resultados em arquivos JSON/HTML, sem banco de dados

### Trabalhos Futuros

- Implementar embeddings + vector store (ChromaDB/FAISS) para políticas extensas
- Adicionar paralelismo com `asyncio` ou `concurrent.futures` para processamento em lote
- Integrar LLM-as-judge como camada adicional de validação nos guardrails
- Adicionar API REST (FastAPI) para integração com sistemas existentes
- Implementar feedback loop para melhoria contínua dos prompts
- Adicionar testes unitários e de integração com pytest
- Monitoramento de drift nas classificações dos agentes

---

## Licença

Projeto desenvolvido para o desafio Future Minds 3. Uso interno e educacional.

---

<p align="center">
  <strong>FinGuard</strong> — Future Minds 3 | Grupo 14<br>
  Desenvolvido por Rafhael Prates Parra Cieto<br>
  rafhael.cieto@zup.com.br
</p>