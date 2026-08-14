import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from containers.application import ApplicationContainer
from core.exceptions import AppError
from settings import settings
from utils.configure_sentry import configure_sentry
from utils.database import close_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

container = ApplicationContainer()

configure_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    nats_client = container.nats_client()
    callback_request_consumer = container.callback_request_consumer()

    try:
        await nats_client.connect()
        await nats_client.setup()
        await callback_request_consumer.start()

        yield
    finally:
        await callback_request_consumer.stop()
        await nats_client.close()
        await close_database()


app = FastAPI(title=settings.app_title, debug=settings.debug, lifespan=lifespan)


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.errors()})
