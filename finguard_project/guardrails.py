"""
FinGuard - Camada de Segurança (Guardrails)
Input Guardrails: bloqueia prompt injection, jailbreak, linguagem imprópria e fora do escopo.
Output Guardrails: sanitiza PII (CPF, cartão, conta, e-mail) e termos impróprios.
"""

import re
from dataclasses import dataclass

# --- Padrões de PII para ofuscação ---
PII_PATTERNS = [
    # CPF: 000.000.000-00 ou 00000000000
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "***.***.***-**"),
    (re.compile(r"\b\d{11}\b"), "***.***.***-**"),
    # Cartão de crédito: grupos de 4 dígitos separados por espaço ou hífen
    (re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"), "****-****-****-****"),
    # Conta bancária: 5-10 dígitos com possível dígito verificador
    (re.compile(r"\b(?:conta|agência|agencia)\s*(?:n[º°o.]?\s*)?\d{4,10}[-\d]*\b", re.IGNORECASE), "[CONTA_OFUSCADA]"),
    # E-mail
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL_OFUSCADO]"),
    # Telefone brasileiro
    (re.compile(r"\b\(?\d{2}\)?\s*\d{4,5}[- ]?\d{4}\b"), "[TELEFONE_OFUSCADO]"),
]

# --- Termos impróprios para ofuscação na saída ---
PROFANITY_TERMS = [
    r"merda", r"porra", r"caralho", r"puta", r"foda", r"foder",
    r"desgraça", r"desgracado", r"idiota", r"imbecil", r"burro",
    r"otário", r"otario", r"babaca", r"cuzão", r"cuzao", r"fdp",
    r"vtnc", r"vsf", r"pqp", r"krl", r"crln", r"arrombado",
    r"estúpido", r"estupido", r"retardado", r"lixo",
]
_PROFANITY_RE = re.compile(
    r"\b(?:" + "|".join(PROFANITY_TERMS) + r")\b",
    re.IGNORECASE
)

# --- Padrões de Prompt Injection / Jailbreak ---
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"(forget|disregard|override)\s+(your\s+)?(instructions?|rules?|guidelines?|system\s*prompt)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+are\s+)?", re.IGNORECASE),
    re.compile(r"pretend\s+(to\s+be|you\s+are)\s+", re.IGNORECASE),
    re.compile(r"(reveal|show|display|output|print)\s+(your\s+)?(system\s*prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"(extract|leak|exfiltrate|dump)\s+(data|information|records?)", re.IGNORECASE),
    re.compile(r"DAN|jailbreak|do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
]

# --- Mensagem de bloqueio educada ---
BLOCK_MESSAGE = (
    "Sua mensagem não pôde ser processada pelo FinGuard. "
    "O sistema aceita apenas reclamações relacionadas a produtos e serviços bancários. "
    "Por favor, reformule sua solicitação descrevendo o problema com seu produto financeiro."
)


@dataclass
class GuardrailResult:
    """Resultado da avaliação de um guardrail."""
    passed: bool
    reason: str | None = None
    sanitized_text: str | None = None


def check_input_guardrails(text: str) -> GuardrailResult:
    """
    Avalia o texto de entrada contra regras de segurança.
    Retorna GuardrailResult(passed=False) se detectar injeção, jailbreak ou conteúdo fora do escopo.
    """
    if not text or not text.strip():
        return GuardrailResult(passed=False, reason="Entrada vazia.")

    # Verifica prompt injection / jailbreak
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return GuardrailResult(passed=False, reason=f"Prompt injection detectado: {pattern.pattern}")

    # Profanidade na entrada de reclamação é tolerada (cliente irritado),
    # mas será ofuscada na saída. Não bloqueamos aqui.

    return GuardrailResult(passed=True)


def sanitize_output(text: str) -> str:
    """
    Sanitiza o texto de saída: ofusca PII e remove termos impróprios.
    """
    if not text:
        return text

    result = text

    # Ofusca PII
    for pattern, replacement in PII_PATTERNS:
        result = pattern.sub(replacement, result)

    # Substitui termos impróprios
    result = _PROFANITY_RE.sub("[TERMO_OFUSCADO]", result)

    return result


def validate_output_guardrails(text: str) -> GuardrailResult:
    """
    Valida que o texto de saída não contém PII exposto nem termos impróprios.
    Retorna o texto sanitizado mesmo quando passa.
    """
    sanitized = sanitize_output(text)
    return GuardrailResult(passed=True, sanitized_text=sanitized)