# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from contextlib import asynccontextmanager

import argparse
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from module.logger import logger

from module.server.home_router import home_app
from module.server.script_router import script_app
from starlette import status
from starlette.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()
app = FastAPI(
    title='OAS',
    description='OAS web service',
    version='0.0.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(home_app)
app.include_router(script_app)


async def on_startup():
    logger.info('OAS web service startup done')


async def on_shutdown():
    logger.info('OAS web service shutdown done')


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Server Error: ", exc_info=True)

    message = ', '.join(str(arg) for arg in exc.args) if exc.args else str(exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            'message': message
        },
    )


def fastapi_app():
    parser = argparse.ArgumentParser(description="OAS web service")
    parser.add_argument(
        "-k", "--key", type=str, help="Password of OAS. No password by default"
    )
    parser.add_argument(
        "--cdn",
        action="store_true",
        help="Use jsdelivr cdn for pywebio static files (css, js). Self host cdn by default.",
    )
    parser.add_argument(
        "--run",
        nargs="+",
        type=str,
        help="Run OAS by config names on startup",
    )
    args, _ = parser.parse_known_args()

    return app
