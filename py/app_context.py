import asyncio
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from networkdevice import ShureNetworkDevice


class AppContext:
    """Encapsulates shared application state previously kept as globals.

    This is a transitional structure to reduce cross‑module globals while
    keeping the existing threaded architecture intact.
    """

    def __init__(self) -> None:
        # List[ShureNetworkDevice]
        self.network_devices: List['ShureNetworkDevice'] = []
        # Queue for messages from sockets to parser
        self.device_message_queue: asyncio.Queue = asyncio.Queue()
