from fastapi import APIRouter

from app.api.v1 import (
    auth,
    boards,
    health,
    interactions,
    moderation,
    notifications,
    posts,
    search,
    tags,
    topics,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(boards.router)
api_router.include_router(topics.router)
api_router.include_router(users.router)
api_router.include_router(posts.router)
api_router.include_router(interactions.router)
api_router.include_router(notifications.router)
api_router.include_router(search.router)
api_router.include_router(tags.router)
api_router.include_router(moderation.router)
