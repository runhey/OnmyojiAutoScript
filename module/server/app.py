# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import argparse
from fastapi import FastAPI

from module.logger import logger

from module.server.home_router import home_app
from module.server.script_router import script_app

app = FastAPI(
    title='OAS',
    description='OAS web service',
    version='0.0.0',
)
app.include_router(home_app)
app.include_router(script_app)

@app.on_event("startup")
async def startup_event():
    logger.info('OAS web service startup done')
    pass

@app.on_event("shutdown")
async def shutdown_event():
    logger.info('OAS web service shutdown done')


















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
