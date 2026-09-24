"""
FinGuard - Motor de RAG para Política Interna
Carrega e indexa o PDF da política interna para consulta pelos agentes.
Usa busca por palavras-chave e trechos relevantes sem dependência de vector DB externo.
"""

import re
from pathlib import Path
from pypdf import PdfReader
from functools import lru_cache

import config


class PolicyRAGEngine:
    """Motor de RAG simples baseado em extração de texto e busca por seções."""

    def __init__(self, pdf_path: Path | None = None):
        self.pdf_path = pdf_path or config.POLICY_PDF_PATH
        self._sections: list[dict] = []
        self._full_text: str = ""
        self._load()

    def _load(self) -> None:
        """Extrai texto do PDF e segmenta em seções numeradas."""
        reader = PdfReader(str(self.pdf_path))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            # Normaliza espaços extras causados pela extração do PDF
            text = re.sub(r" {2,}", " ", text)
            pages_text.append(text)

        self._full_text = "\n".join(pages_text)

        # Segmenta por seções numeradas (ex: "2.1", "3.4", "4.2")
        section_pattern = re.compile(
            r"(\d+(?:\.\d+)?\.?\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]*)", re.MULTILINE
        )
        matches = list(section_pattern.finditer(self._full_text))

        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self._full_text)
            content = self._full_text[start:end].strip()
            self._sections.append({"title": title, "content": content})

    @lru_cache(maxsize=64)
    def query(self, keywords: str, max_results: int = 3) -> str:
        """
        Busca trechos relevantes da política por palavras-chave.
        Retorna os trechos mais relevantes concatenados.
        """
        if not keywords or not keywords.strip():
            return self._get_overview()

        terms = [t.lower() for t in keywords.split() if len(t) > 2]
        scored = []

        for section in self._sections:
            text_lower = section["content"].lower()
            score = sum(1 for term in terms if term in text_lower)
            if score > 0:
                scored.append((score, section))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = scored[:max_results]

        if not results:
            return self._get_overview()

        output_parts = []
        for _, section in results:
            # Limita tamanho de cada trecho para não exceder contexto do LLM
            content = section["content"][:800]
            output_parts.append(f"[{section['title']}]\n{content}")

        return "\n\n---\n\n".join(output_parts)

    def _get_overview(self) -> str:
        """Retorna resumo geral da política quando nenhuma busca específica é feita."""
        overview_sections = ["1.", "2.", "5.", "6."]
        parts = []
        for section in self._sections:
            for prefix in overview_sections:
                if section["title"].startswith(prefix):
                    parts.append(f"[{section['title']}]\n{section['content'][:600]}")
                    break
        return "\n\n---\n\n".join(parts) if parts else self._full_text[:2000]

    def get_sla_info(self, urgencia: str, produto: str | None = None) -> str:
        """
        Retorna informações específicas de SLA para uma combinação de urgência e produto.
        """
        keywords = f"{urgencia}"
        if produto:
            keywords += f" {produto}"
        keywords += " prazo resposta ações imediatas SLA"
        return self.query(keywords, max_results=4)

    @property
    def full_text(self) -> str:
        return self._full_text