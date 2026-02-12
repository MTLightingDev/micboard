import asyncio
import logging

import config
import tornado_server
import shure
import discover
from app_context import AppContext


async def main_async():
    # Initialize shared application context and bind shure module globals to it
    ctx = AppContext()
    shure.init(ctx)

    config.config()

    # Start Shure service tasks in the background
    asyncio.create_task(shure.watchdog_monitor())
    asyncio.create_task(shure.WirelessQueryQueue())
    asyncio.create_task(shure.SocketService())
    asyncio.create_task(shure.ProcessRXMessageQueue())

    # Start async discovery (replaces previous background thread)
    asyncio.create_task(discover.discover_async())

    # Start Tornado server integrated with asyncio loop
    await tornado_server.start_async()


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logging.info("Shutting down...")


if __name__ == '__main__':
    main()
