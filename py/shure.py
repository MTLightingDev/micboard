import time
import select
import queue
import atexit
import sys
import logging
import asyncio
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from app_context import AppContext
    from channel import ChannelDevice
    from networkdevice import ShureNetworkDevice

from networkdevice import ShureNetworkDevice
from channel import chart_update_list, data_update_list
# from mic import WirelessMic
# from iem import IEM

# These will be rebound by shure.init(ctx) to the AppContext-managed state.
NetworkDevices: List[ShureNetworkDevice] = []
DeviceMessageQueue: queue.Queue = queue.Queue()


def init(ctx: 'AppContext') -> None:
    """Bind module-level references to the provided application context.

    This keeps the existing API surface while removing hard globals from the rest of the app.
    """
    global NetworkDevices, DeviceMessageQueue
    NetworkDevices = ctx.network_devices
    DeviceMessageQueue = ctx.device_message_queue


def get_network_device_by_ip(ip: str) -> Optional[ShureNetworkDevice]:
    return next((x for x in NetworkDevices if x.ip == ip), None)

def get_network_device_by_slot(slot: int) -> Optional['ChannelDevice']:
    for networkdevice in NetworkDevices:
        for channel in networkdevice.channels:
            if channel.slot == slot:
                return channel
    return None

def check_add_network_device(ip: str, type: str) -> ShureNetworkDevice:
    net = get_network_device_by_ip(ip)
    if net:
        return net

    net = ShureNetworkDevice(ip, type)
    NetworkDevices.append(net)
    return net

async def watchdog_monitor() -> None:
    while True:
        for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTED'):
            if (int(time.monotonic()) - rx.socket_watchdog) > 5:
                logging.debug('disconnected from: %s', rx.ip)
                rx.socket_disconnect()

        for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTING'):
            if (int(time.monotonic()) - rx.socket_watchdog) > 2:
                rx.socket_disconnect()


        for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'DISCONNECTED'):
            if (int(time.monotonic()) - rx.socket_watchdog) > 20:
                rx.socket_connect()
        await asyncio.sleep(1)

async def WirelessQueryQueue() -> None:
    while True:
        for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTED'):
            strings = rx.get_query_strings()
            for string in strings:
                rx.writeQueue.put(string)
        await asyncio.sleep(10)

async def ProcessRXMessageQueue() -> None:
    while True:
        try:
            # Using loop.run_in_executor for queue.get() if it blocks, 
            # but since we want to move to async, eventually we should use asyncio.Queue
            rx, msg = DeviceMessageQueue.get_nowait()
            rx.parse_raw_rx(msg)
        except queue.Empty:
            await asyncio.sleep(0.1)

async def SocketService() -> None:
    for rx in NetworkDevices:
        rx.socket_connect()

    while True:
        readrx = [rx for rx in NetworkDevices if rx.rx_com_status in ['CONNECTING', 'CONNECTED']]
        writerx = [rx for rx in readrx if not rx.writeQueue.empty()]

        if not readrx and not writerx:
            await asyncio.sleep(0.5)
            continue

        # Non-blocking select check (timeout 0)
        read_socks, write_socks, error_socks = select.select(readrx, writerx, readrx, 0)

        for rx in read_socks:
            try:
                data = rx.f.recv(1024).decode('UTF-8')
            except Exception as e:
                logging.warning("RX socket error from %s: %s", rx.ip, e)
                rx.socket_disconnect()
                break

            d = '>'
            if rx.type == 'uhfr':
                d = '*'
            data = [e+d for e in data.split(d) if e]

            for line in data:
                DeviceMessageQueue.put((rx, line))

            rx.socket_watchdog = int(time.monotonic())
            rx.set_rx_com_status('CONNECTED')

        for rx in write_socks:
            try:
                string = rx.writeQueue.get_nowait()
                logging.debug("write: %s data: %s", rx.ip, string)
                if rx.type in ['qlxd', 'ulxd', 'axtd', 'p10t']:
                    rx.f.sendall(bytearray(string, 'UTF-8'))
                elif rx.type == 'uhfr':
                    rx.f.sendto(bytearray(string, 'UTF-8'), (rx.ip, 2202))
            except queue.Empty:
                pass
            except Exception as e:
                logging.warning("TX error to %s: %s", rx.ip, e)

        for rx in error_socks:
            rx.set_rx_com_status('DISCONNECTED')

        await asyncio.sleep(0.1)



# @atexit.register
def on_exit():
    connected = [rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTED']
    for rx in connected:
        rx.disable_metering()
    time.sleep(50)
    print("IT DONE!")
    sys.exit(0)

# atexit.register(on_exit)
# signal.signal(signal.SIGTERM, on_exit)
# signal.signal(signal.SIGINT, on_exit)
