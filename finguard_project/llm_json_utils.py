"""Utilitários para parse robusto de JSON gerado por LLMs pequenos."""

import json
import re


def _extract_first_json_object(text: str) -> str | None:
    """Extrai o primeiro objeto JSON completo do texto, ignorando conteúdo extra.
    Retorna None quando não encontra } balanceado (resposta truncada)."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None  # truncado — sem } balanceado


def _sanitize_json_string(text: str) -> str:
    """Remove trailing commas e caracteres de controle verdadeiramente problemáticos."""
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Mantém \n, \r, \t — apenas remove control chars raros
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text


def _unescape_json_string_escapes(text: str) -> str:
    """Converte sequências de escape de string JSON em chars literais.
    Usado quando o inner JSON vem do texto RAW (ainda com escapes do outer string)."""
    # Ordem importa: processar \\ antes de \" para evitar double-unescape
    result = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == '"':
                result.append('"')
                i += 2
            elif nxt == "n":
                result.append("\n")
                i += 2
            elif nxt == "t":
                result.append("\t")
                i += 2
            elif nxt == "r":
                result.append("\r")
                i += 2
            elif nxt == "\\":
                result.append("\\")
                i += 2
            else:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _extract_inner_from_wrapper(text: str) -> str | None:
    """Fallback para wrapper {'resposta': '...inner json...'} com aspas não-escaped.
    Encontra o primeiro { após 'resposta': ' e extrai o JSON interno."""
    m = re.search(r'"resposta"\s*:\s*"', text)
    if not m:
        return None
    inner_start = text.find("{", m.end())
    if inner_start == -1:
        return None
    raw_inner = _extract_first_json_object(text[inner_start:])
    if raw_inner is None:
        return None
    return _unescape_json_string_escapes(raw_inner)


def robust_json_loads(text: str) -> dict:
    """Parse JSON com fallbacks progressivos para saídas sujas de LLMs pequenos.

    Fallback 1 — extração string-aware + json.loads strict=False
    Fallback 2 — sanitize (trailing commas, control chars) + json.loads
    Fallback 3 — detecção de wrapper {'resposta': '<inner>'} bem-formado
    Fallback 4 — bypass de wrapper corrompido (aspas não-escaped no outer string)
    """
    extracted = _extract_first_json_object(text)

    result = None
    if extracted is not None:
        try:
            result = json.loads(extracted, strict=False)
        except json.JSONDecodeError:
            try:
                result = json.loads(_sanitize_json_string(extracted), strict=False)
            except json.JSONDecodeError:
                result = None

    # Fallback 3: wrapper {'resposta': '<inner>'} parseable normalmente
    if result is not None:
        if isinstance(result, dict) and len(result) <= 3 and "resposta" in result:
            inner = result["resposta"]
            if isinstance(inner, str) and "{" in inner:
                inner_extracted = _extract_first_json_object(inner)
                if inner_extracted:
                    try:
                        return json.loads(inner_extracted, strict=False)
                    except json.JSONDecodeError:
                        try:
                            return json.loads(_sanitize_json_string(inner_extracted), strict=False)
                        except json.JSONDecodeError:
                            pass
            # inner é prose ou inner JSON inválido — retorna o outer (nivel_risco será None)
            return result
        return result

    # Fallback 4: outer JSON inválido (aspas não-escaped) — bypass direto do inner
    inner_text = _extract_inner_from_wrapper(text)
    if inner_text:
        try:
            return json.loads(inner_text, strict=False)
        except json.JSONDecodeError:
            try:
                return json.loads(_sanitize_json_string(inner_text), strict=False)
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError("Nenhum JSON válido encontrado", text, 0)
