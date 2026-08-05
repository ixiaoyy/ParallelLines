from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pdfplumber
import pytesseract
from fastapi import UploadFile
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pytesseract import Output
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from starlette.requests import Request

from app.core.config import Settings
from app.core.exceptions import AppError, ValidationError
from app.models.user import User
from app.services.pdf_translation_provider import (
    PdfTranslationProvider,
    PdfTranslationSource,
    configured_pdf_translation_provider,
    contains_cjk,
)
from app.services.spam import SpamPreventionService

SAFE_OUTPUT_STEM_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
CJK_SPACE_PATTERN = re.compile(
    r"(?<=[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff])\s+"
    r"(?=[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff])"
)
MAX_RENDERED_PAGE_PIXELS = 48_000_000
MAX_RENDERED_DOCUMENT_PIXELS = 320_000_000


@dataclass(frozen=True)
class PdfBox:
    x0: float
    top: float
    x1: float
    bottom: float

    @property
    def width(self) -> float:
        """Return this top-origin PDF box width in points; side effect: none."""
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        """Return this top-origin PDF box height in points; side effect: none."""
        return max(0.0, self.bottom - self.top)

    @property
    def area(self) -> float:
        """Return this top-origin PDF box area in square points; side effect: none."""
        return self.width * self.height


@dataclass(frozen=True)
class PdfLayoutSegment:
    id: str
    page_index: int
    text: str
    box: PdfBox
    font_size: float
    bold: bool
    source_kind: str


@dataclass(frozen=True)
class PreparedPdf:
    page_images: tuple[Path, ...]
    page_sizes: tuple[tuple[float, float], ...]
    segments: tuple[PdfLayoutSegment, ...]


@dataclass(frozen=True)
class PdfTranslationArtifact:
    content: bytes
    filename: str
    page_count: int
    translated_segments: int


class PdfTranslationService:
    def __init__(self, settings: Settings, spam_service: SpamPreventionService) -> None:
        """Create a stateless PDF translation workflow with runtime limits and rate limiting."""
        self.settings = settings
        self.spam_service = spam_service

    async def translate(
        self,
        file: UploadFile,
        *,
        current_user: User,
        request: Request | None,
        provider: PdfTranslationProvider | None = None,
    ) -> PdfTranslationArtifact:
        """Translate one uploaded Chinese PDF and return a verified English-only artifact.

        Key parameters are the multipart file, authenticated owner, request context, and
        optional test provider. The return value contains in-memory PDF bytes and safe
        download metadata. Side effects are rate-limit recording, model calls, and
        short-lived files that are deleted when this method exits.
        """
        await self.spam_service.enforce_pdf_translation(request, current_user=current_user)
        content = await self._read_limited(file)
        output_filename = english_output_filename(file.filename or "document.pdf")
        translation_provider = provider or configured_pdf_translation_provider(self.settings)

        with tempfile.TemporaryDirectory(prefix="parallellines-pdf-") as raw_temp_dir:
            temp_dir = Path(raw_temp_dir).resolve()
            source_path = temp_dir / "source.pdf"
            source_path.write_bytes(content)
            page_count = await asyncio.to_thread(validate_source_pdf, content, self.settings)
            prepared = await asyncio.to_thread(
                prepare_pdf,
                source_path,
                temp_dir,
                page_count,
                self.settings,
            )
            sources = [
                PdfTranslationSource(id=item.id, text=item.text)
                for item in prepared.segments
            ]
            glossary = await translation_provider.build_glossary(sources)
            translations = await translate_in_batches(
                translation_provider,
                sources,
                glossary,
                batch_chars=self.settings.pdf_translation_batch_chars,
                max_concurrency=self.settings.pdf_translation_max_concurrency,
            )
            output = await asyncio.to_thread(
                build_english_pdf,
                prepared,
                translations,
            )
            await asyncio.to_thread(
                verify_english_pdf,
                output,
                temp_dir,
                page_count,
                self.settings,
            )
        return PdfTranslationArtifact(
            content=output,
            filename=output_filename,
            page_count=page_count,
            translated_segments=len(translations),
        )

    async def _read_limited(self, file: UploadFile) -> bytes:
        """Read one upload within the PDF-specific byte limit and validate its signature.

        Key parameter is a FastAPI upload stream. The return value contains all source
        bytes in memory. Side effect: consumes the upload stream and raises safe 422
        errors for empty, oversized, non-PDF, or mismatched files.
        """
        content = await file.read(self.settings.pdf_translation_max_bytes + 1)
        if len(content) > self.settings.pdf_translation_max_bytes:
            raise ValidationError(
                "pdf_translation_too_large",
                "PDF 文件过大",
                {"max_bytes": self.settings.pdf_translation_max_bytes},
            )
        if not content:
            raise ValidationError("pdf_translation_empty", "请选择一个非空 PDF 文件")
        if not content.startswith(b"%PDF-"):
            raise ValidationError("pdf_translation_invalid_pdf", "文件内容不是有效 PDF")
        filename = (file.filename or "").lower()
        if filename and not filename.endswith(".pdf"):
            raise ValidationError("pdf_translation_invalid_pdf", "只支持 .pdf 文件")
        if file.content_type not in {None, "", "application/pdf", "application/octet-stream"}:
            raise ValidationError("pdf_translation_invalid_pdf", "文件 MIME 类型不是 PDF")
        return content


def validate_source_pdf(content: bytes, settings: Settings) -> int:
    """Validate PDF encryption, page count, and bounded page dimensions.

    Key parameters are source bytes and runtime limits. The return value is the page
    count. Side effect: parses the untrusted PDF with pypdf and raises safe 422 errors.
    """
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise ValidationError(
                "pdf_translation_encrypted",
                "暂不支持加密或需要密码的 PDF",
            )
        page_count = len(reader.pages)
        if page_count < 1:
            raise ValidationError("pdf_translation_invalid_pdf", "PDF 中没有可处理的页面")
        if page_count > settings.pdf_translation_max_pages:
            raise ValidationError(
                "pdf_translation_too_many_pages",
                "PDF 页数超过当前限制",
                {"max_pages": settings.pdf_translation_max_pages},
            )
        total_rendered_pixels = 0.0
        for page_number, page in enumerate(reader.pages, start=1):
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            if width <= 0 or height <= 0 or width > 14_400 or height > 14_400:
                raise ValidationError(
                    "pdf_translation_invalid_page_size",
                    "PDF 包含无法安全处理的页面尺寸",
                )
            rendered_pixels = (
                width
                * settings.pdf_translation_render_dpi
                / 72
                * height
                * settings.pdf_translation_render_dpi
                / 72
            )
            if rendered_pixels > MAX_RENDERED_PAGE_PIXELS:
                raise ValidationError(
                    "pdf_translation_page_too_complex",
                    "PDF 页面像素尺寸过大，无法安全 OCR",
                    {"page": page_number},
                )
            total_rendered_pixels += rendered_pixels
        if total_rendered_pixels > MAX_RENDERED_DOCUMENT_PIXELS:
            raise ValidationError(
                "pdf_translation_document_too_complex",
                "PDF 总页面像素量过大，请拆分文档后重试",
            )
        return page_count
    except ValidationError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise ValidationError(
            "pdf_translation_invalid_pdf",
            "PDF 已损坏或结构无法识别",
        ) from exc


def prepare_pdf(
    source_path: Path,
    temp_dir: Path,
    page_count: int,
    settings: Settings,
) -> PreparedPdf:
    """Render source pages and merge text-layer/OCR Chinese layout segments.

    Key parameters are the validated source path, controlled temp directory, expected
    page count, and runtime settings. The return value contains page images, sizes, and
    deduplicated Chinese regions. Side effects: invokes Poppler/Tesseract and writes PNGs
    only under `temp_dir`.
    """
    ensure_pdf_runtime_available()
    page_images = render_pdf_pages(
        source_path,
        temp_dir / "source-pages",
        page_count,
        dpi=settings.pdf_translation_render_dpi,
        timeout_seconds=settings.pdf_translation_render_timeout_seconds,
    )
    page_sizes, text_segments = extract_text_layer_segments(source_path)
    if len(page_sizes) != page_count:
        raise ValidationError(
            "pdf_translation_extract_failed",
            "PDF 页面尺寸提取结果不完整",
        )
    ocr_segments = extract_ocr_segments(
        page_images,
        page_sizes,
        confidence_floor=max(20, settings.pdf_translation_ocr_confidence - 25),
        timeout_seconds=settings.pdf_translation_ocr_timeout_seconds,
    )
    merged = merge_layout_segments(text_segments, ocr_segments)
    if not merged:
        raise ValidationError(
            "pdf_translation_no_chinese",
            "未在 PDF 文本层或页面图像中检测到可翻译的中文",
        )
    return PreparedPdf(
        page_images=tuple(page_images),
        page_sizes=tuple(page_sizes),
        segments=tuple(merged),
    )


def ensure_pdf_runtime_available() -> None:
    """Require Poppler plus English and Simplified-Chinese Tesseract data.

    Key parameters: none. Return value is none. Side effect: probes installed commands
    and configures pytesseract's executable path; raises 503 when strict verification
    cannot run.
    """
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    if not pdftoppm or not tesseract:
        raise AppError(
            "pdf_translation_runtime_unavailable",
            "PDF 渲染或中文 OCR 服务暂时不可用",
            status_code=503,
        )
    pytesseract.pytesseract.tesseract_cmd = tesseract
    try:
        languages = set(pytesseract.get_languages(config=""))
    except (OSError, pytesseract.TesseractError) as exc:
        raise AppError(
            "pdf_translation_ocr_unavailable",
            "中文 OCR 服务暂时不可用",
            status_code=503,
        ) from exc
    if not {"chi_sim", "eng"}.issubset(languages):
        raise AppError(
            "pdf_translation_ocr_unavailable",
            "服务器缺少中文 OCR 语言包",
            status_code=503,
        )


def render_pdf_pages(
    pdf_path: Path,
    output_dir: Path,
    expected_pages: int,
    *,
    dpi: int,
    timeout_seconds: int,
) -> list[Path]:
    """Render a PDF into ordered PNG pages with a bounded Poppler subprocess.

    Key parameters define the controlled source/output paths, expected page count, DPI,
    and deadline. The return value lists rendered PNG paths. Side effects: creates the
    output directory and child PNG files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    executable = shutil.which("pdftoppm")
    if not executable:
        raise AppError(
            "pdf_translation_runtime_unavailable",
            "PDF 渲染服务暂时不可用",
            status_code=503,
        )
    prefix = output_dir / "page"
    try:
        subprocess.run(
            [executable, "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
            check=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            "pdf_translation_render_timeout",
            "PDF 页面渲染超时，请缩小文件后重试",
            status_code=422,
        ) from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValidationError(
            "pdf_translation_render_failed",
            "PDF 页面无法安全渲染",
        ) from exc
    pages = sorted(output_dir.glob("page-*.png"), key=page_image_number)
    if len(pages) != expected_pages:
        raise ValidationError(
            "pdf_translation_render_failed",
            "PDF 页面渲染结果不完整",
        )
    return pages


def page_image_number(path: Path) -> int:
    """Return the numeric page suffix used to sort Poppler output paths; side effect: none."""
    match = re.search(r"-(\d+)\.png$", path.name)
    return int(match.group(1)) if match else 0


def extract_text_layer_segments(
    source_path: Path,
) -> tuple[list[tuple[float, float]], list[PdfLayoutSegment]]:
    """Extract Chinese-bearing line/cell segments from a PDF text layer.

    Key parameter is the validated local source path. Return values are page sizes and
    ordered layout segments in top-origin PDF points. Side effect: parses PDF text with
    pdfplumber but writes nothing.
    """
    page_sizes: list[tuple[float, float]] = []
    segments: list[PdfLayoutSegment] = []
    try:
        with pdfplumber.open(source_path) as document:
            for page_index, page in enumerate(document.pages):
                page_sizes.append((float(page.width), float(page.height)))
                words = page.extract_words(
                    use_text_flow=False,
                    keep_blank_chars=False,
                    extra_attrs=["fontname", "size"],
                )
                page_segments = words_to_layout_segments(words, page_index)
                segments.extend(page_segments)
    except (OSError, ValueError, TypeError) as exc:
        raise ValidationError(
            "pdf_translation_extract_failed",
            "PDF 文本层无法读取",
        ) from exc
    return page_sizes, segments


def words_to_layout_segments(
    words: list[dict[str, object]],
    page_index: int,
) -> list[PdfLayoutSegment]:
    """Group pdfplumber words into visual line/cell segments that contain Chinese.

    Key parameters are untrusted word dictionaries and a zero-based page index. The
    return value contains bounded, ordered layout segments. Side effect: none.
    """
    normalized_words: list[dict[str, object]] = []
    for word in words:
        text = word.get("text")
        try:
            x0 = float(word["x0"])
            x1 = float(word["x1"])
            top = float(word["top"])
            bottom = float(word["bottom"])
        except (KeyError, TypeError, ValueError):
            continue
        if not isinstance(text, str) or not text.strip() or x1 <= x0 or bottom <= top:
            continue
        normalized_words.append(
            {
                **word,
                "text": text.strip(),
                "x0": x0,
                "x1": x1,
                "top": top,
                "bottom": bottom,
            }
        )
    normalized_words.sort(key=lambda word: (round(float(word["top"]), 1), float(word["x0"])))

    lines: list[list[dict[str, object]]] = []
    for word in normalized_words:
        center = (float(word["top"]) + float(word["bottom"])) / 2
        matching_line: list[dict[str, object]] | None = None
        for line in reversed(lines[-8:]):
            line_top = min(float(item["top"]) for item in line)
            line_bottom = max(float(item["bottom"]) for item in line)
            line_center = (line_top + line_bottom) / 2
            word_height = float(word["bottom"]) - float(word["top"])
            tolerance = max(2.5, min(line_bottom - line_top, word_height) * 0.55)
            if abs(center - line_center) <= tolerance:
                matching_line = line
                break
        if matching_line is None:
            lines.append([word])
        else:
            matching_line.append(word)

    segments: list[PdfLayoutSegment] = []
    for line in lines:
        line.sort(key=lambda word: float(word["x0"]))
        chunks: list[list[dict[str, object]]] = [[]]
        for word in line:
            current = chunks[-1]
            if current:
                previous = current[-1]
                gap = float(word["x0"]) - float(previous["x1"])
                height = max(
                    float(word["bottom"]) - float(word["top"]),
                    float(previous["bottom"]) - float(previous["top"]),
                )
                if gap > max(18.0, height * 2.1):
                    chunks.append([])
                    current = chunks[-1]
            current.append(word)
        for chunk in chunks:
            text = join_pdf_words(chunk)
            if not contains_cjk(text):
                continue
            x0 = min(float(item["x0"]) for item in chunk)
            x1 = max(float(item["x1"]) for item in chunk)
            top = min(float(item["top"]) for item in chunk)
            bottom = max(float(item["bottom"]) for item in chunk)
            sizes = [safe_float(item.get("size")) for item in chunk]
            font_size = sum(size for size in sizes if size > 0) / max(
                1, sum(1 for size in sizes if size > 0)
            )
            font_names = [str(item.get("fontname") or "").lower() for item in chunk]
            segments.append(
                PdfLayoutSegment(
                    id="",
                    page_index=page_index,
                    text=compact_cjk_spaces(text),
                    box=PdfBox(x0=x0, top=top, x1=x1, bottom=bottom),
                    font_size=font_size or max(6.0, (bottom - top) * 0.78),
                    bold=any("bold" in name or "black" in name for name in font_names),
                    source_kind="text",
                )
            )
    segments.sort(key=lambda item: (item.box.top, item.box.x0))
    return [
        PdfLayoutSegment(
            id=f"p{page_index + 1}-t{index + 1}",
            page_index=item.page_index,
            text=item.text,
            box=item.box,
            font_size=item.font_size,
            bold=item.bold,
            source_kind=item.source_kind,
        )
        for index, item in enumerate(segments)
    ]


def join_pdf_words(words: list[dict[str, object]]) -> str:
    """Join ordered PDF words while preserving natural Latin spaces and Chinese adjacency.

    Key parameter is one ordered visual chunk. The return value is a compact source
    string suitable for translation. Side effect: none.
    """
    parts: list[str] = []
    previous: dict[str, object] | None = None
    for word in words:
        text = str(word["text"])
        if previous is not None:
            gap = float(word["x0"]) - float(previous["x1"])
            previous_text = str(previous["text"])
            if gap > 1.2 and not (contains_cjk(previous_text[-1:]) and contains_cjk(text[:1])):
                parts.append(" ")
        parts.append(text)
        previous = word
    return "".join(parts).strip()


def extract_ocr_segments(
    page_images: list[Path],
    page_sizes: list[tuple[float, float]],
    *,
    confidence_floor: int,
    timeout_seconds: int,
) -> list[PdfLayoutSegment]:
    """Extract Chinese OCR line segments from rendered pages, including image watermarks.

    Key parameters are ordered PNGs, matching PDF sizes, a confidence floor, and a
    per-page OCR deadline. The return value uses top-origin PDF-point coordinates.
    Side effect: invokes Tesseract once per page and decodes each PNG.
    """
    segments: list[PdfLayoutSegment] = []
    for page_index, image_path in enumerate(page_images):
        try:
            with Image.open(image_path) as raw_image:
                image = raw_image.convert("RGB")
                if image.width * image.height > MAX_RENDERED_PAGE_PIXELS:
                    raise ValidationError(
                        "pdf_translation_page_too_complex",
                        "PDF 页面像素尺寸过大，无法安全 OCR",
                    )
                data = pytesseract.image_to_data(
                    image,
                    lang="chi_sim+eng",
                    config="--psm 11",
                    output_type=Output.DICT,
                    timeout=timeout_seconds,
                )
                page_width, page_height = page_sizes[page_index]
                grouped = group_ocr_words(data, confidence_floor=confidence_floor)
                for line_index, words in enumerate(grouped, start=1):
                    text = compact_cjk_spaces(" ".join(str(item["text"]) for item in words))
                    if not contains_cjk(text):
                        continue
                    left = min(int(item["left"]) for item in words)
                    top = min(int(item["top"]) for item in words)
                    right = max(int(item["left"]) + int(item["width"]) for item in words)
                    bottom = max(int(item["top"]) + int(item["height"]) for item in words)
                    box = PdfBox(
                        x0=left * page_width / image.width,
                        top=top * page_height / image.height,
                        x1=right * page_width / image.width,
                        bottom=bottom * page_height / image.height,
                    )
                    segments.append(
                        PdfLayoutSegment(
                            id=f"p{page_index + 1}-o{line_index}",
                            page_index=page_index,
                            text=text,
                            box=box,
                            font_size=max(6.0, box.height * 0.76),
                            bold=box.height >= 16,
                            source_kind="ocr",
                        )
                    )
        except ValidationError:
            raise
        except (OSError, RuntimeError, ValueError, pytesseract.TesseractError) as exc:
            raise AppError(
                "pdf_translation_ocr_failed",
                f"第 {page_index + 1} 页中文 OCR 失败",
                status_code=503,
            ) from exc
    return segments


def group_ocr_words(
    data: dict[str, list[object]],
    *,
    confidence_floor: int,
) -> list[list[dict[str, object]]]:
    """Group trustworthy Tesseract word records by block, paragraph, and line IDs.

    Key parameters are `image_to_data` columns and a confidence floor. The return value
    is reading-order OCR lines with normalized numeric coordinates. Side effect: none.
    """
    groups: dict[tuple[int, int, int], list[dict[str, object]]] = defaultdict(list)
    count = len(data.get("text", []))
    required_keys = {
        "text",
        "conf",
        "left",
        "top",
        "width",
        "height",
        "block_num",
        "par_num",
        "line_num",
    }
    if not required_keys.issubset(data):
        return []
    for index in range(count):
        text = str(data["text"][index]).strip()
        confidence = safe_float(data["conf"][index])
        if not text or confidence < confidence_floor:
            continue
        try:
            record = {
                "text": text,
                "left": int(data["left"][index]),
                "top": int(data["top"][index]),
                "width": int(data["width"][index]),
                "height": int(data["height"][index]),
            }
            key = (
                int(data["block_num"][index]),
                int(data["par_num"][index]),
                int(data["line_num"][index]),
            )
        except (TypeError, ValueError):
            continue
        if record["width"] <= 0 or record["height"] <= 0:
            continue
        groups[key].append(record)
    ordered = sorted(
        groups.values(),
        key=lambda words: (
            min(int(item["top"]) for item in words),
            min(int(item["left"]) for item in words),
        ),
    )
    for words in ordered:
        words.sort(key=lambda item: int(item["left"]))
    return ordered


def merge_layout_segments(
    text_segments: list[PdfLayoutSegment],
    ocr_segments: list[PdfLayoutSegment],
) -> list[PdfLayoutSegment]:
    """Merge text-layer and OCR segments while discarding OCR duplicates.

    Key parameters are ordered text and OCR regions. The return value preserves text-layer
    segments as authoritative and renumbers accepted OCR regions. Side effect: none.
    """
    accepted = list(text_segments)
    ocr_index_by_page: Counter[int] = Counter()
    for ocr_segment in ocr_segments:
        duplicate = any(
            candidate.page_index == ocr_segment.page_index
            and overlap_ratio(candidate.box, ocr_segment.box) >= 0.35
            for candidate in text_segments
        )
        if duplicate:
            continue
        ocr_index_by_page[ocr_segment.page_index] += 1
        accepted.append(
            PdfLayoutSegment(
                id=f"p{ocr_segment.page_index + 1}-o{ocr_index_by_page[ocr_segment.page_index]}",
                page_index=ocr_segment.page_index,
                text=ocr_segment.text,
                box=ocr_segment.box,
                font_size=ocr_segment.font_size,
                bold=ocr_segment.bold,
                source_kind=ocr_segment.source_kind,
            )
        )
    accepted.sort(key=lambda item: (item.page_index, item.box.top, item.box.x0))
    return accepted


def overlap_ratio(left: PdfBox, right: PdfBox) -> float:
    """Return intersection area divided by the smaller non-empty box area; side effect: none."""
    intersection_width = max(0.0, min(left.x1, right.x1) - max(left.x0, right.x0))
    intersection_height = max(0.0, min(left.bottom, right.bottom) - max(left.top, right.top))
    smaller_area = min(left.area, right.area)
    if smaller_area <= 0:
        return 0.0
    return intersection_width * intersection_height / smaller_area


async def translate_in_batches(
    provider: PdfTranslationProvider,
    sources: list[PdfTranslationSource],
    glossary: dict[str, str],
    *,
    batch_chars: int,
    max_concurrency: int,
) -> dict[str, str]:
    """Translate ordered source segments in bounded concurrent provider batches.

    Key parameters are the provider, sources, shared glossary, character budget, and
    concurrency cap. The return value maps every source ID to English. Side effect:
    performs bounded concurrent model requests.
    """
    batches = build_translation_batches(sources, max_chars=batch_chars)
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def translate_batch(batch: list[PdfTranslationSource]) -> dict[str, str]:
        """Translate one bounded batch while holding the provider concurrency slot."""
        async with semaphore:
            return await provider.translate(batch, glossary)

    translated_batches = await asyncio.gather(*(translate_batch(batch) for batch in batches))
    merged: dict[str, str] = {}
    for translated in translated_batches:
        overlap = merged.keys() & translated.keys()
        if overlap:
            raise AppError(
                "pdf_translation_contract_failed",
                "PDF 翻译结果包含重复文本区域",
                status_code=503,
            )
        merged.update(translated)
    expected_ids = {source.id for source in sources}
    if merged.keys() != expected_ids:
        raise AppError(
            "pdf_translation_contract_failed",
            "PDF 翻译结果不完整",
            status_code=503,
        )
    return merged


def build_translation_batches(
    sources: list[PdfTranslationSource],
    *,
    max_chars: int,
) -> list[list[PdfTranslationSource]]:
    """Partition ordered segments without splitting a source string across model calls.

    Key parameters are ordered sources and a positive character budget. The return value
    is a non-empty list of bounded batches. Side effect: none.
    """
    budget = max(500, max_chars)
    batches: list[list[PdfTranslationSource]] = []
    current: list[PdfTranslationSource] = []
    current_chars = 0
    for source in sources:
        source_chars = len(source.text) + len(source.id) + 40
        if current and (current_chars + source_chars > budget or len(current) >= 80):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(source)
        current_chars += source_chars
    if current:
        batches.append(current)
    return batches


def build_english_pdf(
    prepared: PreparedPdf,
    translations: dict[str, str],
) -> bytes:
    """Rebuild page-aligned English PDF pages over rasterized source backgrounds.

    Key parameters are prepared page assets/layout and verified translations. The return
    value is a static PDF byte string with ASCII metadata and selectable English text.
    Side effect: decodes source PNGs in memory and writes a ReportLab canvas.
    """
    output = BytesIO()
    first_size = prepared.page_sizes[0]
    canvas = Canvas(output, pagesize=first_size, pageCompression=1)
    canvas.setTitle("English Translation")
    canvas.setAuthor("ParallelLines")
    canvas.setSubject("Verified English-only PDF translation")
    canvas.setCreator("ParallelLines PDF Translation Tool")
    by_page: dict[int, list[PdfLayoutSegment]] = defaultdict(list)
    for segment in prepared.segments:
        by_page[segment.page_index].append(segment)

    for page_index, image_path in enumerate(prepared.page_images):
        page_width, page_height = prepared.page_sizes[page_index]
        canvas.setPageSize((page_width, page_height))
        with Image.open(image_path) as raw_image:
            image = raw_image.convert("RGB")
            canvas.drawImage(
                ImageReader(image),
                0,
                0,
                width=page_width,
                height=page_height,
                preserveAspectRatio=False,
                mask="auto",
            )
            for segment in by_page.get(page_index, []):
                english = translations.get(segment.id)
                if not english:
                    raise AppError(
                        "pdf_translation_contract_failed",
                        "PDF 翻译结果缺少页面文本",
                        status_code=503,
                    )
                draw_translated_segment(
                    canvas,
                    image,
                    page_width,
                    page_height,
                    segment,
                    english,
                )
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def draw_translated_segment(
    canvas: Canvas,
    image: Image.Image,
    page_width: float,
    page_height: float,
    segment: PdfLayoutSegment,
    english: str,
) -> None:
    """Mask one Chinese layout box and fit its English translation into the same region.

    Key parameters are the output canvas, source raster, page geometry, layout segment,
    and verified ASCII English. Return value is none. Side effects: paints one background
    mask and one or more selectable English text lines on the current PDF page.
    """
    box = expanded_box(segment.box, page_width, page_height, padding=1.4)
    background = sampled_background_color(image, box, page_width, page_height)
    foreground = sampled_foreground_color(
        image,
        segment.box,
        page_width,
        page_height,
        background,
    )
    canvas.setFillColor(Color(*background))
    canvas.rect(
        box.x0,
        page_height - box.bottom,
        box.width,
        box.height,
        fill=1,
        stroke=0,
    )

    canvas.setFillColor(Color(*foreground))
    font_name = "Helvetica-Bold" if segment.bold or segment.font_size >= 15 else "Helvetica"
    initial_size = min(30.0, max(5.0, segment.font_size))
    lines, font_size = fit_text_lines(
        english,
        font_name,
        box.width,
        box.height,
        initial_size=initial_size,
        minimum_size=4.2,
    )
    line_height = font_size * 1.08
    baseline = page_height - box.top - font_size
    canvas.setFont(font_name, font_size)
    for line in lines:
        canvas.drawString(box.x0 + 0.6, baseline, line)
        baseline -= line_height


def fit_text_lines(
    text: str,
    font_name: str,
    width: float,
    height: float,
    *,
    initial_size: float,
    minimum_size: float,
) -> tuple[list[str], float]:
    """Fit ASCII text into a fixed PDF box by wrapping and reducing the font size.

    Key parameters define text, font, box size, and font-size bounds. Return values are
    wrapped lines plus the selected size. Raises a safe layout error instead of deleting
    or truncating content when the original region cannot hold the English translation.
    Side effect: queries ReportLab font metrics.
    """
    safe_width = max(4.0, width - 1.2)
    safe_height = max(4.0, height - 0.8)
    size = initial_size
    while size >= minimum_size:
        lines = wrap_text(text, font_name, size, safe_width)
        lines_fit_width = all(
            pdfmetrics.stringWidth(line, font_name, size) <= safe_width for line in lines
        )
        if lines and lines_fit_width and len(lines) * size * 1.08 <= safe_height:
            return lines, size
        size -= 0.4
    raise ValidationError(
        "pdf_translation_layout_overflow",
        "英文译文无法在不删减内容的情况下保持原版面，请换用留白更充分的 PDF",
    )


def wrap_text(text: str, font_name: str, font_size: float, width: float) -> list[str]:
    """Wrap space-delimited ASCII text to a measured ReportLab width; side effect: none."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= width:
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return lines


def expanded_box(
    box: PdfBox,
    page_width: float,
    page_height: float,
    *,
    padding: float,
) -> PdfBox:
    """Return a page-bounded box expanded equally on every side; side effect: none."""
    return PdfBox(
        x0=max(0.0, box.x0 - padding),
        top=max(0.0, box.top - padding),
        x1=min(page_width, box.x1 + padding),
        bottom=min(page_height, box.bottom + padding),
    )


def sampled_background_color(
    image: Image.Image,
    box: PdfBox,
    page_width: float,
    page_height: float,
) -> tuple[float, float, float]:
    """Estimate a mask color from raster pixels immediately surrounding a text box.

    Key parameters are the RGB page image, point-space box, and page dimensions. The
    return value is a normalized RGB tuple. Side effect: samples but does not mutate pixels.
    """
    left, top, right, bottom = point_box_to_pixel_bounds(
        image,
        box,
        page_width,
        page_height,
    )
    padding = max(2, round(image.width / page_width * 1.8))
    outer_left = max(0, left - padding)
    outer_right = min(image.width, right + padding)
    outer_top = max(0, top - padding)
    outer_bottom = min(image.height, bottom + padding)
    pixels: list[tuple[int, int, int]] = []
    for y in range(outer_top, outer_bottom):
        for x in range(outer_left, outer_right):
            if left <= x < right and top <= y < bottom:
                continue
            pixel = image.getpixel((x, y))
            if isinstance(pixel, tuple) and len(pixel) >= 3:
                pixels.append((int(pixel[0]), int(pixel[1]), int(pixel[2])))
    if not pixels:
        return (1.0, 1.0, 1.0)
    return dominant_pixel_color(pixels)


def sampled_foreground_color(
    image: Image.Image,
    box: PdfBox,
    page_width: float,
    page_height: float,
    background: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Estimate original text color inside a layout box, preserving faint watermarks.

    Key parameters are the RGB source image, original text box, page dimensions, and
    sampled background. The return value is normalized RGB with a contrast fallback.
    Side effect: samples but does not mutate pixels.
    """
    left, top, right, bottom = point_box_to_pixel_bounds(
        image,
        box,
        page_width,
        page_height,
    )
    background_bytes = tuple(round(channel * 255) for channel in background)
    candidates: list[tuple[int, int, int]] = []
    for y in range(top, bottom):
        for x in range(left, right):
            pixel = image.getpixel((x, y))
            if not isinstance(pixel, tuple) or len(pixel) < 3:
                continue
            rgb = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
            if max(abs(rgb[index] - background_bytes[index]) for index in range(3)) >= 18:
                candidates.append(rgb)
    if candidates:
        return dominant_pixel_color(candidates)
    background_luminance = (
        0.2126 * background[0] + 0.7152 * background[1] + 0.0722 * background[2]
    )
    return (1.0, 1.0, 1.0) if background_luminance < 0.42 else (0.11, 0.16, 0.23)


def point_box_to_pixel_bounds(
    image: Image.Image,
    box: PdfBox,
    page_width: float,
    page_height: float,
) -> tuple[int, int, int, int]:
    """Map a top-origin PDF-point box to page-image pixel bounds; side effect: none."""
    return (
        max(0, round(box.x0 * image.width / page_width)),
        max(0, round(box.top * image.height / page_height)),
        min(image.width, round(box.x1 * image.width / page_width)),
        min(image.height, round(box.bottom * image.height / page_height)),
    )


def dominant_pixel_color(
    pixels: list[tuple[int, int, int]],
) -> tuple[float, float, float]:
    """Return the mean actual RGB color inside the most common coarse color bucket.

    Key parameter is a non-empty RGB pixel list. The normalized return value preserves
    exact white and dark source colors instead of replacing them with bucket midpoints.
    Side effect: none.
    """
    buckets = Counter((red // 16, green // 16, blue // 16) for red, green, blue in pixels)
    dominant_bucket = buckets.most_common(1)[0][0]
    selected = [
        pixel
        for pixel in pixels
        if tuple(channel // 16 for channel in pixel) == dominant_bucket
    ]
    count = len(selected)
    return tuple(sum(pixel[index] for pixel in selected) / count / 255 for index in range(3))


def verify_english_pdf(
    content: bytes,
    temp_dir: Path,
    expected_pages: int,
    settings: Settings,
) -> None:
    """Require zero Chinese in output metadata/text and high-confidence rendered OCR.

    Key parameters are output bytes, controlled temp directory, expected page count, and
    OCR settings. Return value is none. Side effects: parses and re-renders the final PDF;
    raises a safe 503 instead of releasing an unverifiable artifact.
    """
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if len(reader.pages) != expected_pages:
            raise AppError(
                "pdf_translation_output_invalid",
                "英文 PDF 页数与原文件不一致",
                status_code=503,
            )
        searchable_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        metadata_text = " ".join(str(value) for value in (reader.metadata or {}).values())
    except AppError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise AppError(
            "pdf_translation_output_invalid",
            "英文 PDF 生成后无法重新读取",
            status_code=503,
        ) from exc
    if contains_cjk(searchable_text) or contains_cjk(metadata_text):
        raise AppError(
            "pdf_translation_chinese_residue",
            "英文 PDF 文本层仍检测到中文，已阻止下载",
            status_code=503,
        )

    output_path = temp_dir / "english-output.pdf"
    output_path.write_bytes(content)
    pages = render_pdf_pages(
        output_path,
        temp_dir / "verification-pages",
        expected_pages,
        dpi=settings.pdf_translation_render_dpi,
        timeout_seconds=settings.pdf_translation_render_timeout_seconds,
    )
    residue_pages = ocr_cjk_residue_pages(
        pages,
        confidence_floor=settings.pdf_translation_ocr_confidence,
        timeout_seconds=settings.pdf_translation_ocr_timeout_seconds,
    )
    if residue_pages:
        raise AppError(
            "pdf_translation_chinese_residue",
            "英文 PDF 页面仍检测到中文，已阻止下载",
            status_code=503,
            details={"pages": residue_pages},
        )


def ocr_cjk_residue_pages(
    pages: Iterable[Path],
    *,
    confidence_floor: int,
    timeout_seconds: int,
) -> list[int]:
    """Return one-based page numbers with high-confidence Chinese OCR residue.

    Key parameters are rendered page paths, the strict confidence floor, and the
    per-page deadline. The return value is ordered and deduplicated. Side effect:
    invokes Tesseract on every page.
    """
    residue: list[int] = []
    for page_index, page_path in enumerate(pages, start=1):
        try:
            with Image.open(page_path) as raw_image:
                data = pytesseract.image_to_data(
                    raw_image.convert("RGB"),
                    lang="chi_sim+eng",
                    config="--psm 11",
                    output_type=Output.DICT,
                    timeout=timeout_seconds,
                )
        except (OSError, RuntimeError, ValueError, pytesseract.TesseractError) as exc:
            raise AppError(
                "pdf_translation_ocr_failed",
                f"英文 PDF 第 {page_index} 页复核失败",
                status_code=503,
            ) from exc
        texts = data.get("text", [])
        confidences = data.get("conf", [])
        for text, confidence in zip(texts, confidences, strict=False):
            if safe_float(confidence) >= confidence_floor and contains_cjk(str(text)):
                residue.append(page_index)
                break
    return residue


def english_output_filename(original_filename: str) -> str:
    """Return a stable ASCII download filename derived from an untrusted source name.

    Key parameter is the browser-provided filename. The return value always ends in
    `-english.pdf` and contains no path separators or non-ASCII text. Side effect: none.
    """
    stem = Path(original_filename.replace("\\", "/")).name
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4]
    ascii_stem = stem.encode("ascii", "ignore").decode()
    safe_stem = SAFE_OUTPUT_STEM_PATTERN.sub("-", ascii_stem).strip("-._")[:80]
    return f"{safe_stem or 'document'}-english.pdf"


def compact_cjk_spaces(value: str) -> str:
    """Remove OCR-introduced spaces only between adjacent Chinese characters; side effect: none."""
    normalized = " ".join(value.split())
    return CJK_SPACE_PATTERN.sub("", normalized)


def safe_float(value: object) -> float:
    """Convert an untrusted numeric field to float, returning zero on failure; side effect: none."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
