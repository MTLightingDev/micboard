import queue


class AppContext:
    """Encapsulates shared application state previously kept as globals.

    This is a transitional structure to reduce cross‑module globals while
    keeping the existing threaded architecture intact.
    """

    def __init__(self):
        # List[ShureNetworkDevice]
        self.network_devices = []
        # Queue for messages from sockets to parser
        self.device_message_queue = queue.Queue()
