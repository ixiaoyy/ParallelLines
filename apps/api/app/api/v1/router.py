from fastapi import APIRouter

from app.api.seo import api_seo_router
from app.api.v1 import (
    admin,
    ai,
    analytics,
    api_docs,
    auth,
    boards,
    daily_reports,
    drafts,
    email,
    events,
    health,
    integrations,
    interactions,
    invites,
    localization,
    migrations,
    moderation,
    notifications,
    pdf_translations,
    posts,
    search,
    site,
    tags,
    topics,
    uploads,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(api_docs.router)
api_router.include_router(auth.router)
api_router.include_router(email.router)
api_router.include_router(events.router)
api_router.include_router(boards.router)
api_router.include_router(topics.router)
api_router.include_router(users.router)
api_router.include_router(posts.router)
api_router.include_router(interactions.router)
api_router.include_router(integrations.router)
api_router.include_router(localization.router)
api_router.include_router(invites.router)
api_router.include_router(notifications.router)
api_router.include_router(search.router)
api_router.include_router(tags.router)
api_router.include_router(moderation.router)
api_router.include_router(migrations.router)
api_router.include_router(uploads.router)
api_router.include_router(admin.router)
api_router.include_router(ai.router)
api_router.include_router(daily_reports.router)
api_router.include_router(pdf_translations.router)
api_router.include_router(analytics.router)
api_router.include_router(site.router)
api_router.include_router(drafts.router)
api_router.include_router(api_seo_router)
