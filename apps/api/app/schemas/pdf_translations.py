from pydantic import BaseModel

from app.core.config import Settings


class PdfTranslationCapabilities(BaseModel):
    ai_enabled: bool
    max_bytes: int
    max_pages: int
    privacy_notice: str

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        ai_enabled: bool,
    ) -> "PdfTranslationCapabilities":
        """Build the user-visible PDF limits and processing disclosure from settings.

        Key parameters are runtime settings and whether a server credential is available.
        The return value is safe for browsers and never includes model credentials.
        Side effect: none.
        """
        return cls(
            ai_enabled=ai_enabled,
            max_bytes=settings.pdf_translation_max_bytes,
            max_pages=settings.pdf_translation_max_pages,
            privacy_notice=(
                "文件仅用于本次转换，会在受控临时目录处理并于请求结束后删除；"
                "中文文本和 OCR 内容会发送到站点配置的模型服务。"
            ),
        )
