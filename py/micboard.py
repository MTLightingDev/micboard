import threading
import time
import asyncio
import logging

import config
import tornado_server
import shure
import discover
from app_context import AppContext


async def main_async():
    config.config()

    # Initialize shared application context and bind shure module globals to it
    ctx = AppContext()
    shure.init(ctx)

    # Start Shure service tasks in the background
    asyncio.create_task(shure.watchdog_monitor())
    asyncio.create_task(shure.WirelessQueryQueue())
    asyncio.create_task(shure.SocketService())
    asyncio.create_task(shure.ProcessRXMessageQueue())
    
    # discover.discover is currently blocking, we can run it in a thread for now 
    # or refactor it to be async.
    discover_t = threading.Thread(target=discover.discover, daemon=True)
    discover_t.start()

    # Start Tornado server
    # tornado_server.twisted() starts its own IOLoop by default.
    # We should adapt it to use the current asyncio loop.
    await tornado_server.start_async()


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logging.info("Shutting down...")


if __name__ == '__main__':
    main()
