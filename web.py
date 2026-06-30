"""
Minimal aiohttp server to keep the Render free-tier instance alive.

Render spins down free web services after 15 minutes of inactivity.
Point an external uptime service (e.g. cron-job.org, UptimeRobot) at
GET /health every 10–14 minutes to prevent spin-down.
"""
import logging

from aiohttp import web

log = logging.getLogger(__name__)


async def _handle_ping(request: web.Request) -> web.Response:  # noqa: ARG001
    return web.Response(text="OK", content_type="text/plain")


async def start_web_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    app = web.Application()
    app.router.add_get("/", _handle_ping)
    app.router.add_get("/health", _handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("Keep-alive web server listening on %s:%d", host, port)
