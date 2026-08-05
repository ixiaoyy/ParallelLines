from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.schemas.common import ApiResponse
from app.schemas.pdf_translations import PdfTranslationCapabilities
from app.services.pdf_translation_provider import pdf_translation_provider_configured
from app.services.pdf_translations import PdfTranslationService
from app.services.spam import SpamPreventionService
from app.services.uploads import content_disposition

router = APIRouter(prefix="/pdf-translations", tags=["pdf-translations"])


@router.get(
    "/capabilities",
    response_model=ApiResponse[PdfTranslationCapabilities],
)
async def get_pdf_translation_capabilities(
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PdfTranslationCapabilities]:
    """Return safe PDF limits and provider availability for an authenticated user.

    Key parameters are injected settings and authentication. The return value contains
    no credentials or provider content. Side effect: none beyond authentication.
    """
    del current_user
    return ApiResponse(
        data=PdfTranslationCapabilities.from_settings(
            settings,
            ai_enabled=pdf_translation_provider_configured(settings),
        )
    )


@router.post(
    "",
    response_class=Response,
    responses={
        200: {
            "description": "Verified English-only PDF",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {"schema": {"type": "string"}},
                "X-PDF-Page-Count": {"schema": {"type": "integer"}},
                "X-PDF-Translated-Segments": {"schema": {"type": "integer"}},
            },
        }
    },
)
async def translate_pdf_to_english(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    file: Annotated[UploadFile, File(description="Chinese PDF to translate")],
) -> Response:
    """Translate one authenticated user's PDF and return a non-persistent download.

    Key parameters are the multipart source file plus request/session dependencies. The
    return value is a no-store binary PDF response. Side effects are rate-limit recording,
    temporary processing, OCR, and configured model calls; no file row is persisted.
    """
    service = PdfTranslationService(
        settings,
        SpamPreventionService(session, settings),
    )
    artifact = await service.translate(
        file,
        current_user=current_user,
        request=request,
    )
    return Response(
        artifact.content,
        media_type="application/pdf",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Content-Disposition": content_disposition(artifact.filename, inline=False),
            "X-Content-Type-Options": "nosniff",
            "X-PDF-Page-Count": str(artifact.page_count),
            "X-PDF-Translated-Segments": str(artifact.translated_segments),
        },
    )
