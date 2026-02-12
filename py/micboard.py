import asyncio
import logging
import signal

import config
import tornado_server
import shure
import discover
from app_context import AppContext


async def main_async():
    # Initialize shared application context and bind shure module globals to it
    ctx = AppContext()
    ctx.device_message_queue = asyncio.Queue()
    shure.init(ctx)

    config.config()

    # Start Shure service tasks in the background
    tasks = [
        asyncio.create_task(shure.watchdog_monitor()),
        asyncio.create_task(shure.WirelessQueryQueue()),
        asyncio.create_task(shure.SocketService()),
        asyncio.create_task(shure.ProcessRXMessageQueue()),
        asyncio.create_task(discover.discover_async())
    ]

    def stop():
        logging.info("Shutdown signal received...")
        if tornado_server.shutdown_event:
            tornado_server.shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop)

    # Start Tornado server integrated with asyncio loop
    try:
        await tornado_server.start_async()
    except asyncio.CancelledError:
        logging.info("Tornado task cancelled")
    finally:
        logging.info("Cleaning up...")
        # Stop all background tasks
        for task in tasks:
            task.cancel()
    
        # Tornado server shutdown is already handled by await tornado_server.start_async() returning
    
        await asyncio.gather(*tasks, return_exceptions=True)

        # Final exit logic (disable metering, etc.)
        # shure.on_exit() is best-effort synchronous send, but let's make it safe
        # shure.on_exit()


def main():
    try:
        asyncio.run(main_async())
    except Exception as e:
        logging.error("Unhandled exception: %s", e)


if __name__ == '__main__':
    main()
