from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        results = self.store.search(question, top_k=top_k)
        if not results:
            return "Không tìm thấy thông tin phù hợp trong cơ sở tri thức."

        context_blocks = []
        for index, result in enumerate(results, start=1):
            metadata = result.get("metadata", {})
            source = (
                metadata.get("source_url")
                or metadata.get("source")
                or metadata.get("doc_id")
                or result.get("id", "unknown")
            )
            title = metadata.get("title", result.get("id", "Tài liệu"))
            context_blocks.append(
                f"[{index}] {title}\nNguồn: {source}\n{result['content']}"
            )

        prompt = (
            "Bạn là trợ lý hỏi đáp dựa trên tài liệu. Chỉ sử dụng ngữ cảnh "
            "được cung cấp; nếu ngữ cảnh không đủ, hãy nói rõ không tìm thấy "
            "thông tin. Trích dẫn nguồn bằng số [1], [2], ... cho từng khẳng định.\n\n"
            "NGỮ CẢNH:\n"
            + "\n\n".join(context_blocks)
            + f"\n\nCÂU HỎI: {question}\nTRẢ LỜI:"
        )
        return self.llm_fn(prompt)
