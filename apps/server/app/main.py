from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import bootstrap
from .routers import experiments, git, papers, projects, reading_notes, settings, system, tasks, workspace


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap.init_database()
    yield


app = FastAPI(title="RoboResearch Workbench Local API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"(moz-extension://.*|http://127\.0\.0\.1(:\d+)?|http://localhost(:\d+)?)",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    system.router,
    settings.router,
    projects.router,
    git.router,
    tasks.router,
    experiments.router,
    papers.router,
    reading_notes.router,
    workspace.router,
):
    app.include_router(router)
