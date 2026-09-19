"""Benchmark retrieval strategies on the cleaned VinUniversity library corpus.

The script uses a deterministic lexical hashing embedder so the benchmark is
repeatable and requires no API key.  It is more meaningful than the lab's
random MockEmbedder for these controlled questions, but it is not a semantic
embedding model; that limitation is recorded in both reports.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from src import Document, EmbeddingStore, FixedSizeChunker, RecursiveChunker, SentenceChunker


CORPUS_DIR = Path("data/university")


@dataclass(frozen=True)
class BenchmarkCase:
    query: str
    gold_answer: str
    gold_doc_id: str
    answer_marker: str
    metadata_filter: dict[str, str] | None = None


BENCHMARK_CASES = [
    BenchmarkCase(
        query="Tôi được mượn tối đa bao nhiêu tài liệu và trong bao lâu?",
        gold_answer="Sinh viên đại học được mượn 3 tài liệu trong 2 tuần.",
        gold_doc_id="02-undergraduate-borrowing",
        answer_marker="3 tài liệu",
        metadata_filter={"audience": "student"},
    ),
    BenchmarkCase(
        query="Thời gian gia hạn tài liệu được tính thế nào và cần điều kiện gì?",
        gold_answer="Bằng một nửa thời hạn ban đầu; tài liệu chưa quá hạn và không có người khác yêu cầu.",
        gold_doc_id="03-material-types-and-renewal",
        answer_marker="một nửa thời hạn",
    ),
    BenchmarkCase(
        query="Sách Course Reserve được mượn tối đa bao lâu và bao nhiêu cuốn mỗi lần?",
        gold_answer="2 giờ và 1 cuốn mỗi người mỗi lần.",
        gold_doc_id="03-material-types-and-renewal",
        answer_marker="2 giờ",
    ),
    BenchmarkCase(
        query="Tài liệu tôi yêu cầu được thư viện giữ bao lâu trước khi hủy yêu cầu?",
        gold_answer="Thư viện giữ trong 2 ngày.",
        gold_doc_id="04-requesting-items",
        answer_marker="2 ngày",
    ),
    BenchmarkCase(
        query="Có thể đặt phòng chức năng trước bao lâu và đến muộn bao nhiêu phút thì bị hủy?",
        gold_answer="Đặt trước tối đa 1 tuần; đến muộn quá 10 phút thì bị hủy.",
        gold_doc_id="06-rooms-and-equipment",
        answer_marker="10 phút",
    ),
]


def normalize_text(text: str) -> str:
    """Lowercase and remove Vietnamese accents for robust marker matching."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


class LexicalHashEmbedder:
    """Dependency-free hashing-vector embedder for reproducible local evaluation."""

    STOP_WORDS = {
        "a", "bi", "bao", "cach", "can", "cua", "co", "duoc", "gi", "khi",
        "la", "lam", "mot", "nay", "nhieu", "nhung", "the", "thi", "toi",
        "trong", "va", "voi",
    }
    CANONICAL = {
        "cuon": "tai_lieu",
        "sach": "tai_lieu",
        "documents": "tai_lieu",
        "borrow": "muon",
        "borrowing": "muon",
        "renewal": "gia_han",
        "renewals": "gia_han",
        "phong": "phong",
        "room": "phong",
        "rooms": "phong",
        "request": "yeu_cau",
        "requests": "yeu_cau",
        "sinh": "sinh_vien",
        "student": "sinh_vien",
        "students": "sinh_vien",
    }

    def __init__(self, dimension: int = 4096) -> None:
        self.dimension = dimension
        self._backend_name = f"lexical-hashing-{dimension}"

    def _tokens(self, text: str) -> list[str]:
        raw = re.findall(r"[a-z0-9_]+", normalize_text(text))
        tokens = [self.CANONICAL.get(token, token) for token in raw if token not in self.STOP_WORDS]
        return tokens + [f"{left}::{right}" for left, right in zip(tokens, tokens[1:])]

    def __call__(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in self._tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            vector[int.from_bytes(digest, "big") % self.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class HeadingChunker:
    """Keep Markdown sections intact, recursively splitting oversized sections."""

    def __init__(self, chunk_size: int = 420) -> None:
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        sections = [part.strip() for part in re.split(r"(?=^#{1,6}\s)", text, flags=re.MULTILINE) if part.strip()]
        chunks: list[str] = []
        for section in sections:
            lines = section.splitlines()
            heading = lines[0] if lines and lines[0].startswith("#") else ""
            if len(section) <= self.chunk_size:
                chunks.append(section)
                continue

            body = "\n".join(lines[1:]).strip() if heading else section
            body_size = max(80, self.chunk_size - len(heading) - 1)
            for piece in RecursiveChunker(chunk_size=body_size).chunk(body):
                chunks.append(f"{heading}\n{piece}".strip())
        return chunks


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"Missing YAML frontmatter: {path}")
    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, parts[2].strip()


def make_chunker(strategy: str):
    if strategy == "fixed":
        return FixedSizeChunker(chunk_size=420, overlap=80)
    if strategy == "sentence":
        return SentenceChunker(max_sentences_per_chunk=3)
    if strategy == "recursive":
        return RecursiveChunker(chunk_size=420)
    if strategy == "heading":
        return HeadingChunker(chunk_size=420)
    raise ValueError(f"Unknown strategy: {strategy}")


def build_store(strategy: str) -> tuple[EmbeddingStore, int]:
    chunker = make_chunker(strategy)
    documents: list[Document] = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        metadata, content = parse_frontmatter(path)
        for index, chunk in enumerate(chunker.chunk(content)):
            documents.append(
                Document(
                    id=f"{path.stem}#{index}",
                    content=chunk,
                    metadata={**metadata, "doc_id": path.stem, "chunk_index": index},
                )
            )
    store = EmbeddingStore(f"library_{strategy}", embedding_fn=LexicalHashEmbedder())
    store.add_documents(documents)
    return store, len(documents)


def result_has_answer(result: dict, case: BenchmarkCase) -> bool:
    same_document = result["metadata"].get("doc_id") == case.gold_doc_id
    has_marker = normalize_text(case.answer_marker) in normalize_text(result["content"])
    return same_document and has_marker


def concise_answer(results: list[dict], case: BenchmarkCase) -> str:
    for result in results:
        if result_has_answer(result, case):
            paragraphs = [part.strip() for part in result["content"].split("\n\n") if part.strip()]
            for paragraph in paragraphs:
                if normalize_text(case.answer_marker) in normalize_text(paragraph):
                    return paragraph.replace("\n", " ")
    return "Không tìm thấy đủ thông tin trong top-3."


def run_strategy(strategy: str, verbose: bool = True) -> tuple[int, list[int]]:
    store, chunk_count = build_store(strategy)
    scores: list[int] = []
    if verbose:
        print(f"=== Strategy: {strategy} | backend: lexical-hashing-4096 | chunks: {chunk_count} ===")

    for number, case in enumerate(BENCHMARK_CASES, start=1):
        results = store.search_with_filter(case.query, top_k=3, metadata_filter=case.metadata_filter)
        relevant_rank = next((rank for rank, result in enumerate(results, 1) if result_has_answer(result, case)), None)
        score = 2 if relevant_rank == 1 else 1 if relevant_rank in (2, 3) else 0
        scores.append(score)
        if verbose:
            print(f"\nQ{number}: {case.query}")
            print(f"filter={case.metadata_filter} | benchmark_score={score}/2")
            for rank, result in enumerate(results, start=1):
                print(
                    f"  {rank}. score={result['score']:.4f} "
                    f"doc_id={result['metadata']['doc_id']} chunk={result['metadata']['chunk_index']}"
                )
            print(f"  answer: {concise_answer(results, case)}")

        if number == 1 and verbose:
            unfiltered = store.search(case.query, top_k=3)
            print("  A/B without audience filter:")
            for rank, result in enumerate(unfiltered, start=1):
                print(
                    f"    {rank}. score={result['score']:.4f} "
                    f"doc_id={result['metadata']['doc_id']} audience={result['metadata']['audience']}"
                )

    if verbose:
        print(f"\nTOTAL: {sum(scores)}/10 | top-3 answer-bearing: {sum(score > 0 for score in scores)}/5")
    return chunk_count, scores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=["fixed", "sentence", "recursive", "heading"], default="heading")
    parser.add_argument("--all", action="store_true", help="Compare all four strategies")
    args = parser.parse_args()

    if args.all:
        print("strategy,chunks,score")
        for strategy in ("fixed", "sentence", "recursive", "heading"):
            chunks, scores = run_strategy(strategy, verbose=False)
            print(f"{strategy},{chunks},{sum(scores)}/10")
        print()
    run_strategy(args.strategy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
