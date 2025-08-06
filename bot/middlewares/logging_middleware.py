import logging
import uuid
import time
import contextvars
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter to inject the correlation_id into log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get()
        return True


# Configure logger with structured data filter
logger = logging.getLogger(__name__)
logger.addFilter(CorrelationIdFilter())

# Helper used throughout the middleware to create human-readable key=value
# strings that are also easy to assert against in unit-tests.


def _fmt_ctx(ctx: Dict[str, Any]) -> str:
    """Return a deterministic key=value string used in log messages."""
    return " ".join(f"{k}={v}" for k, v in ctx.items() if v is not None)


class LoggingMiddleware(BaseMiddleware):
    """
    This middleware logs incoming updates with structured logs,
    correlation IDs, performance metrics, FSM states, and rate-limiting info.
    """

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        cid = str(uuid.uuid4())
        correlation_id_ctx.set(cid)
        data["correlation_id"] = cid

        user = data.get("event_from_user")
        user_id = getattr(user, "id", None)

        # Extract FSM state if available
        fsm_state = None
        fsm = data.get("state")
        if fsm:
            try:
                fsm_state = await fsm.get_state()
            except Exception:
                fsm_state = None

        # Log the incoming update with structured context
        incoming_ctx = {
            "correlation_id": cid,
            "user_id": user_id,
            "update_type": event.event_type,
            "update_id": event.update_id,
            "fsm_state": fsm_state,
        }

        logger.info(
            f"Incoming update {_fmt_ctx(incoming_ctx)}",
            extra=incoming_ctx,
        )

        def _clean_state(s: Any) -> str:
            raw = str(s)
            if raw.startswith("<State '") and raw.endswith("'>"):
                return raw[len("<State '") : -2]
            return raw

        prev_state = data.get("previous_state")
        current_state_hint = data.get("state") or fsm_state
        if prev_state is not None and current_state_hint is not None and prev_state != current_state_hint:
            transition_ctx = {
                "correlation_id": cid,
                "user_id": user_id,
            }
            logger.info(
                f"FSM transition {_clean_state(prev_state)} -> {_clean_state(current_state_hint)} {_fmt_ctx(transition_ctx)}",
                extra=transition_ctx,
            )

        start_time = time.monotonic()
        try:
            result = await handler(event, data)
            return result

        except TelegramRetryAfter as e:
            # Rate limiting log
            warn_ctx = {
                "correlation_id": data["correlation_id"],
                "user_id": getattr(data.get("event_from_user"), "id", None),
                "update_type": event.event_type,
                "update_id": event.update_id,
                "retry_after": e.retry_after,
            }
            logger.warning(
                f"Rate limit exceeded (HTTP 429) {_fmt_ctx(warn_ctx)}",
                extra=warn_ctx,
            )
            raise

        except TelegramAPIError as e:
            # Telegram API error log
            err_ctx = {
                "correlation_id": cid,
                "user_id": user_id,
                "update_type": event.event_type,
                "update_id": event.update_id,
                "error_code": getattr(e, "error_code", None),
                "description": getattr(e, "description", None),
            }
            logger.error(
                f"Telegram API error {_fmt_ctx(err_ctx)}",
                extra=err_ctx,
            )
            raise

        except Exception as e:
            # General exception log with traceback
            exc_ctx = {
                "correlation_id": cid,
                "user_id": user_id,
                "update_type": event.event_type,
                "update_id": event.update_id,
                "error": str(e),
            }
            logger.exception(
                f"Exception caught in handler {_fmt_ctx(exc_ctx)}",
                extra=exc_ctx,
            )
            raise

        finally:
            # Performance metrics and post-processing log
            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # __qualname__ attribute.
            handler_module = getattr(handler, "__module__", "")
            handler_name = getattr(handler, "__qualname__", None)
            if handler_name is None:
                handler_name = handler.__class__.__name__

            if handler_module == "functools" and handler_name == "partial":
                handler_repr = "UNHANDLED"
            else:
                handler_repr = f"{handler_module}.{handler_name}"

            processed_ctx = {
                "correlation_id": cid,
                "user_id": user_id,
                "update_type": event.event_type,
                "update_id": event.update_id,
                "fsm_state": fsm_state,
                "handler": handler_repr,
                "execution_time_ms": elapsed_ms,
            }

            logger.info(
                f"Handler processed {_fmt_ctx(processed_ctx)}",
                extra=processed_ctx,
            )
