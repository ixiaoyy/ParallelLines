from __future__ import annotations

import shutil
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.services.pdf_translation_provider import (
    PdfTranslationSource,
    contains_cjk,
    parse_translation_payload,
)
from app.services.pdf_translations import (
    PdfBox,
    PdfLayoutSegment,
    PreparedPdf,
    build_english_pdf,
    build_translation_batches,
    english_output_filename,
    extract_ocr_segments,
    fit_text_lines,
    sampled_background_color,
    sampled_foreground_color,
    validate_source_pdf,
    verify_english_pdf,
)


def test_pdf_translation_payload_preserves_names_identifiers_dates_and_amounts() -> None:
    sources = [
        PdfTranslationSource(id="company", text="测试科技（惠州）有限公司"),
        PdfTranslationSource(id="person", text="法定代表人：张某某"),
        PdfTranslationSource(id="code", text="统一社会信用代码：91441300MA5ABC1234"),
        PdfTranslationSource(id="date", text="日期：2026年8月5日 金额：人民币10,000.00元"),
    ]
    translations, problems = parse_translation_payload(
        {
            "translations": [
                {"id": "company", "text": "Shi Ce Technology (Huizhou) Co., Ltd."},
                {"id": "person", "text": "Legal Representative: Zhang Moumou"},
                {"id": "code", "text": "Unified Social Credit Code: 91441300MA5ABC1234"},
                {"id": "date", "text": "Date: 2026-08-05; Amount: CNY 10,000.00"},
            ]
        },
        sources,
    )

    assert problems == []
    assert translations["company"] == "Shi Ce Technology (Huizhou) Co., Ltd."
    assert translations["person"].endswith("Zhang Moumou")
    assert "91441300MA5ABC1234" in translations["code"]
    assert all(not contains_cjk(value) and value.isascii() for value in translations.values())


def test_pdf_translation_payload_rejects_chinese_and_missing_numbers() -> None:
    sources = [PdfTranslationSource(id="certificate", text="证书编号：CN-2026-0088")]

    translations, problems = parse_translation_payload(
        {
            "translations": [
                {"id": "certificate", "text": "证书 Number: CN-2026-0089"},
            ]
        },
        sources,
    )

    assert translations == {}
    assert any("empty, non-English, or contains Chinese" in problem for problem in problems)

    translations, problems = parse_translation_payload(
        {
            "translations": [
                {"id": "certificate", "text": "Certificate No.: CN-2026-0089"},
            ]
        },
        sources,
    )

    assert translations == {}
    assert any("missing protected values" in problem for problem in problems)


def test_pdf_layout_never_truncates_translation_text() -> None:
    text = "Unified Social Credit Code: 91441300MA5ABC1234"

    lines, _ = fit_text_lines(
        text,
        "Helvetica",
        180,
        40,
        initial_size=10,
        minimum_size=4.2,
    )

    assert " ".join(lines) == text
    with pytest.raises(ValidationError) as exc_info:
        fit_text_lines(
            text,
            "Helvetica",
            8,
            8,
            initial_size=8,
            minimum_size=4.2,
        )
    assert exc_info.value.code == "pdf_translation_layout_overflow"


def test_pdf_validation_rejects_unsafe_render_dimensions() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=14_400, height=14_400)
    content = BytesIO()
    writer.write(content)

    with pytest.raises(ValidationError) as exc_info:
        validate_source_pdf(content.getvalue(), Settings(environment="test"))

    assert exc_info.value.code == "pdf_translation_page_too_complex"


def test_pdf_mask_colors_preserve_white_background_and_faint_watermark() -> None:
    image = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 60, 60), fill=(225, 230, 235))
    box = PdfBox(x0=40, top=40, x1=61, bottom=61)

    background = sampled_background_color(image, box, 100, 100)
    foreground = sampled_foreground_color(image, box, 100, 100, background)

    assert background == pytest.approx((1.0, 1.0, 1.0))
    assert foreground == pytest.approx((225 / 255, 230 / 255, 235 / 255))


def test_pdf_translation_batches_and_ascii_filename_are_stable() -> None:
    sources = [
        PdfTranslationSource(id=f"item-{index}", text="中文内容" * 20)
        for index in range(7)
    ]

    batches = build_translation_batches(sources, max_chars=500)

    assert [source.id for batch in batches for source in batch] == [source.id for source in sources]
    assert len(batches) > 1
    assert english_output_filename("测试报告 2026/最终版.pdf") == "document-english.pdf"
    assert english_output_filename("patent-report_2026.pdf") == "patent-report_2026-english.pdf"


def test_pdf_rebuild_and_ocr_remove_visible_chinese() -> None:
    runtime = pdf_runtime_fixture()
    if runtime is None:
        pytest.skip("PDF OCR system dependencies or a CJK test font are unavailable")
    cjk_font_path = runtime
    page_width, page_height = (595.0, 842.0)
    image_width, image_height = (1240, 1754)
    with tempfile.TemporaryDirectory(prefix="pdf-translation-test-") as raw_temp_dir:
        temp_dir = Path(raw_temp_dir)
        image_path = temp_dir / "source-page.png"
        image = Image.new("RGB", (image_width, image_height), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(cjk_font_path), 42)
        title_box = draw_text_and_box(draw, (100, 100), "检测报告", font)
        company_box = draw_text_and_box(
            draw,
            (100, 220),
            "测试科技（惠州）有限公司",
            font,
        )
        code_box = draw_text_and_box(draw, (100, 350), "证书编号：CN-2026-0088", font)
        draw.rectangle((90, 320, 1150, 430), outline=(90, 105, 120), width=3)
        image.save(image_path)

        segments = (
            layout_segment(
                "title",
                title_box,
                0,
                image_width,
                image_height,
                page_width,
                page_height,
                20,
            ),
            layout_segment(
                "company",
                company_box,
                0,
                image_width,
                image_height,
                page_width,
                page_height,
                12,
            ),
            layout_segment(
                "code",
                code_box,
                0,
                image_width,
                image_height,
                page_width,
                page_height,
                11,
            ),
        )
        prepared = PreparedPdf(
            page_images=(image_path,),
            page_sizes=((page_width, page_height),),
            segments=segments,
        )
        output = build_english_pdf(
            prepared,
            {
                "title": "TEST REPORT",
                "company": "Shi Ce Technology (Huizhou) Co., Ltd.",
                "code": "Certificate No.: CN-2026-0088",
            },
        )
        settings = Settings(
            environment="test",
            pdf_translation_render_dpi=150,
            pdf_translation_render_timeout_seconds=60,
            pdf_translation_ocr_confidence=45,
        )

        verify_english_pdf(output, temp_dir, 1, settings)

        reader = PdfReader(BytesIO(output))
        extracted = reader.pages[0].extract_text() or ""
        assert len(reader.pages) == 1
        assert "TEST REPORT" in extracted
        assert "CN-2026-0088" in extracted
        assert not contains_cjk(extracted)


def test_ocr_extracts_chinese_from_scanned_page() -> None:
    runtime = pdf_runtime_fixture()
    if runtime is None:
        pytest.skip("PDF OCR system dependencies or a CJK test font are unavailable")
    image = Image.new("RGB", (1000, 700), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(runtime), 54)
    draw.text((80, 100), "专利证书", fill="black", font=font)
    with tempfile.TemporaryDirectory(prefix="pdf-ocr-test-") as raw_temp_dir:
        page_path = Path(raw_temp_dir) / "page-1.png"
        image.save(page_path)
        segments = extract_ocr_segments(
            [page_path],
            [(595.0, 416.5)],
            confidence_floor=20,
            timeout_seconds=30,
        )

    assert segments
    assert any(contains_cjk(segment.text) for segment in segments)


def pdf_runtime_fixture() -> Path | None:
    """Return a usable CJK font only when Poppler and Chinese Tesseract are installed."""
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        return None
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    return next((path for path in candidates if path.is_file()), None)


def draw_text_and_box(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
) -> tuple[int, int, int, int]:
    """Draw one CJK fixture line and return its tight pixel bounding box."""
    draw.text(position, text, fill="black", font=font)
    return draw.textbbox(position, text, font=font)


def layout_segment(
    segment_id: str,
    pixel_box: tuple[int, int, int, int],
    page_index: int,
    image_width: int,
    image_height: int,
    page_width: float,
    page_height: float,
    font_size: float,
) -> PdfLayoutSegment:
    """Map one fixture pixel box to the service's top-origin PDF-point segment."""
    left, top, right, bottom = pixel_box
    return PdfLayoutSegment(
        id=segment_id,
        page_index=page_index,
        text="fixture中文",
        box=PdfBox(
            x0=left * page_width / image_width,
            top=top * page_height / image_height,
            x1=right * page_width / image_width,
            bottom=bottom * page_height / image_height,
        ),
        font_size=font_size,
        bold=segment_id == "title",
        source_kind="ocr",
    )
