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

from device_config import BASE_CONST
from networkdevice import ShureNetworkDevice
from channel import chart_update_list, data_update_list
# from mic import WirelessMic
# from iem import IEM

# These will be rebound by shure.init(ctx) to the AppContext-managed state.
NetworkDevices: List[ShureNetworkDevice] = []
DeviceMessageQueue: Optional[asyncio.Queue] = None


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
    try:
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
    except asyncio.CancelledError:
        pass

async def WirelessQueryQueue() -> None:
    try:
        while True:
            for rx in (rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTED'):
                if not rx.writeQueue:
                    rx.writeQueue = asyncio.Queue()
                strings = rx.get_query_strings()
                for string in strings:
                    rx.writeQueue.put_nowait(string)
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass

async def ProcessRXMessageQueue() -> None:
    try:
        while True:
            rx, msg = await DeviceMessageQueue.get()
            try:
                rx.parse_raw_rx(msg)
            finally:
                DeviceMessageQueue.task_done()
    except asyncio.CancelledError:
        pass

async def SocketService() -> None:
    # Set of active RX tasks to keep track of them
    rx_tasks = set()

    async def handle_rx(rx: ShureNetworkDevice):
        try:
            if not rx.writeQueue:
                rx.writeQueue = asyncio.Queue()
            if BASE_CONST[rx.type]['PROTOCOL'] == 'TCP':
                reader, writer = await asyncio.open_connection(rx.ip, 2202)
                rx.set_rx_com_status('CONNECTED')
                rx.enable_metering(0.1)
                
                # Send initial queries
                for string in rx.get_all():
                    rx.writeQueue.put_nowait(string)

                async def writer_task():
                    try:
                        while True:
                            msg = await rx.writeQueue.get()
                            writer.write(msg.encode('UTF-8'))
                            await writer.drain()
                            rx.writeQueue.task_done()
                    except (asyncio.CancelledError, ConnectionError):
                        pass

                w_task = asyncio.create_task(writer_task())
                
                try:
                    delimiter = '>' if rx.type != 'uhfr' else '*'
                    while True:
                        # Shure messages are delimited by > or *
                        # We can read until the delimiter
                        data = await reader.read(1024)
                        if not data:
                            break
                        
                        decoded = data.decode('UTF-8', errors='ignore')
                        messages = [m + delimiter for m in decoded.split(delimiter) if m]
                        for msg in messages:
                            DeviceMessageQueue.put_nowait((rx, msg))
                        
                        rx.socket_watchdog = int(time.monotonic())
                finally:
                    w_task.cancel()
                    writer.close()
                    await writer.wait_closed()

            elif BASE_CONST[rx.type]['PROTOCOL'] == 'UDP':
                class ShureUDPProtocol(asyncio.DatagramProtocol):
                    def __init__(self, rx, queue):
                        self.rx = rx
                        self.queue = queue
                        self.transport = None

                    def connection_made(self, transport):
                        self.transport = transport
                        self.rx.set_rx_com_status('CONNECTED')
                        self.rx.enable_metering(0.1)
                        # Send initial queries
                        for string in self.rx.get_all():
                            self.transport.sendto(string.encode('UTF-8'))

                    def datagram_received(self, data, addr):
                        delimiter = '*' # uhfr uses *
                        decoded = data.decode('UTF-8', errors='ignore')
                        messages = [m + delimiter for m in decoded.split(delimiter) if m]
                        for msg in messages:
                            self.queue.put_nowait((self.rx, msg))
                        self.rx.socket_watchdog = int(time.monotonic())

                loop = asyncio.get_running_loop()
                transport, protocol = await loop.create_datagram_endpoint(
                    lambda: ShureUDPProtocol(rx, DeviceMessageQueue),
                    remote_addr=(rx.ip, 2202)
                )
                
                try:
                    while True:
                        msg = await rx.writeQueue.get()
                        transport.sendto(msg.encode('UTF-8'))
                        rx.writeQueue.task_done()
                finally:
                    transport.close()

        except Exception as e:
            logging.warning("Connection error to %s: %s", rx.ip, e)
        finally:
            rx.socket_disconnect()

    try:
        while True:
            # Check for new devices and start tasks for them
            for rx in NetworkDevices:
                if rx.rx_com_status == 'DISCONNECTED' and (int(time.monotonic()) - rx.socket_watchdog) > 20:
                    # Mark as connecting to avoid starting multiple tasks
                    rx.set_rx_com_status('CONNECTING')
                    task = asyncio.create_task(handle_rx(rx))
                    rx_tasks.add(task)
                    task.add_done_callback(rx_tasks.discard)
            
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        for task in rx_tasks:
            task.cancel()
        await asyncio.gather(*rx_tasks, return_exceptions=True)



def on_exit():
    logging.info("Sending final commands to devices...")
    connected = [rx for rx in NetworkDevices if rx.rx_com_status == 'CONNECTED']
    for rx in connected:
        rx.disable_metering()
    
    # We need to give the SocketService a moment to send these commands if it's still running,
    # but since we are in a synchronous on_exit called after tasks are cancelled, 
    # we might need a different approach if we want to BE SURE.
    # However, the previous code had time.sleep(50) which is crazy.
    # Let's do a quick synchronous send for those commands.
    for rx in connected:
        try:
            while not rx.writeQueue.empty():
                string = rx.writeQueue.get_nowait()
                if rx.type in ['qlxd', 'ulxd', 'axtd', 'p10t', 'slxd']:
                    rx.f.sendall(bytearray(string, 'UTF-8'))
                elif rx.type == 'uhfr':
                    rx.f.sendto(bytearray(string, 'UTF-8'), (rx.ip, 2202))
        except:
            pass
    
    logging.info("IT DONE!")

# atexit.register(on_exit)
# signal.signal(signal.SIGTERM, on_exit)
# signal.signal(signal.SIGINT, on_exit)
