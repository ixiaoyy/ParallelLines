from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    boards,
    drafts,
    email,
    health,
    interactions,
    invites,
    moderation,
    notifications,
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
api_router.include_router(auth.router)
api_router.include_router(email.router)
api_router.include_router(boards.router)
api_router.include_router(topics.router)
api_router.include_router(users.router)
api_router.include_router(posts.router)
api_router.include_router(interactions.router)
api_router.include_router(invites.router)
api_router.include_router(notifications.router)
api_router.include_router(search.router)
api_router.include_router(tags.router)
api_router.include_router(moderation.router)
api_router.include_router(uploads.router)
api_router.include_router(admin.router)
api_router.include_router(site.router)
api_router.include_router(drafts.router)
