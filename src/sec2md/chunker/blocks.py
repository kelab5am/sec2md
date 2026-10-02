import re
from typing import List, Optional
from pydantic import BaseModel, Field, computed_field

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


def estimate_tokens(text: str) -> int:
    """
    Calculate token count for text.

    Uses tiktoken with cl100k_base encoding (gpt-3.5-turbo/gpt-4) if available.
    Falls back to character/4 heuristic if tiktoken is not installed.
    """
    if TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            return max(1, len(text) // 4)
    else:
        # Fallback: simple heuristic
        return max(1, len(text) // 4)


_SEPARATOR_ROW = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$')


def is_separator_row(line: str) -> bool:
    """Return whether a line is a Markdown table header separator such as ``| --- | --- |``."""
    return bool(_SEPARATOR_ROW.match(line))


def separator_cell_count(line: str) -> int:
    """Number of columns declared by a separator row."""
    return len(line.strip().strip('|').split('|'))


def split_sentences(text: str) -> List[str]:
    """Simple regex-based sentence splitter"""
    # Split on .!? followed by whitespace and capital letter or end of string
    # Handles common abbreviations like Mr., Dr., Inc., etc.
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if s.strip()]


class BaseBlock(BaseModel):
    """Base class for markdown blocks."""
    block_type: str = Field(..., description="Type of markdown block")
    content: str = Field(..., description="Block content")
    page: int = Field(..., description="Page number")
    element_ids: Optional[List[str]] = Field(default=None, description="Element IDs backing this block")

    model_config = {"frozen": False}

    @computed_field
    @property
    def tokens(self) -> int:
        return estimate_tokens(self.content)


class Sentence(BaseModel):
    """Sentence within a text block."""
    content: str = Field(..., description="Sentence content")

    model_config = {"frozen": False}

    @computed_field
    @property
    def tokens(self) -> int:
        return estimate_tokens(self.content)


class TextBlock(BaseBlock):
    block_type: str = Field(default='Text', description="Text block type")

    @computed_field
    @property
    def sentences(self) -> List[Sentence]:
        """Returns the text block sentences"""
        return [Sentence(content=content) for content in split_sentences(self.content)]

    @classmethod
    def from_sentences(cls, sentences: List[Sentence], page: int, element_ids: Optional[List[str]] = None):
        content = " ".join([sentence.content for sentence in sentences])
        return cls(content=content, page=page, block_type='Text', element_ids=element_ids)


class TableBlock(BaseBlock):
    block_type: str = Field(default='Table', description="Table block type")

    def __init__(self, **data):
        if 'content' in data:
            data['content'] = self._to_minified_markdown_static(data['content'])
        super().__init__(**data)

    @staticmethod
    def _to_minified_markdown_static(content: str) -> str:
        """Returns the table in a Minified Markdown format"""
        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            if not line.strip():
                continue

            if is_separator_row(line):
                cleaned_lines.append('|' + '|'.join(['---'] * separator_cell_count(line)) + '|')
                continue

            parts = line.split('|')
            cleaned_parts = [re.sub(r'\s+', ' ', part.strip()) for part in parts]
            cleaned_lines.append('|'.join(cleaned_parts))

        return '\n'.join(cleaned_lines)


class HeaderBlock(BaseBlock):
    block_type: str = Field(default='Header', description="Header block type")
