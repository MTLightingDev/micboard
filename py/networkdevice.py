import asyncio
import socket
import time
from collections import defaultdict
import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from channel import ChannelDevice

from device_config import BASE_CONST
from iem import IEM
from mic import WirelessMic


PORT = 2202


class ShureNetworkDevice:
    def __init__(self, ip: str, type: str) -> None:
        self.ip = ip
        self.type = type
        self.channels: List['ChannelDevice'] = []
        self.rx_com_status = 'DISCONNECTED'
        self.writeQueue: Optional[asyncio.Queue] = None
        self.f: Optional[socket.socket] = None
        self.socket_watchdog = int(time.monotonic())
        self.raw: Dict[str, Any] = defaultdict(dict)
        self.BASECONST: Dict[str, Any] = BASE_CONST[self.type]['base_const']

    def socket_connect(self) -> None:
        # socket_connect is now handled by SocketService in an async way.
        # This method is kept for compatibility if needed, but it's mostly a no-op now
        # or it could just trigger the watchdog to reconnect sooner.
        self.socket_watchdog = int(time.monotonic()) - 21

    def socket_disconnect(self) -> None:
        if self.f:
            try:
                self.f.close()
            except:
                pass
            self.f = None
        self.set_rx_com_status('DISCONNECTED')
        self.socket_watchdog = int(time.monotonic())


    def fileno(self) -> int:
        if self.f:
            return self.f.fileno()
        raise ValueError("Socket is not initialized")

    def set_rx_com_status(self, status: str) -> None:
        self.rx_com_status = status
        # if status == 'CONNECTED':
        #     print("Connected to {} at {}".format(self.ip,datetime.datetime.now()))
        # elif status == 'DISCONNECTED':
        #     print("Disconnected from {} at {}".format(self.ip,datetime.datetime.now()))

    def add_channel_device(self, cfg: Dict[str, Any]) -> None:
        if BASE_CONST[self.type]['DEVICE_CLASS'] == 'WirelessMic':
            self.channels.append(WirelessMic(self, cfg))
        elif BASE_CONST[self.type]['DEVICE_CLASS'] == 'IEM':
            self.channels.append(IEM(self, cfg))

    def get_device_by_channel(self, channel: int) -> Optional['ChannelDevice']:
        return next((x for x in self.channels if x.channel == int(channel)), None)

    def parse_raw_rx(self, data: str) -> None:
        data = data.strip('< >').strip('* ')
        data = data.replace('{', '').replace('}', '')
        data = data.rstrip()
        split = data.split()
        if data:
            try:
                if split[0] in ['REP', 'REPORT', 'SAMPLE'] and split[1] in ['1', '2', '3', '4']:
                    ch = self.get_device_by_channel(int(split[1]))
                    if ch:
                        ch.parse_raw_ch(data)
                    else:
                        logging.debug("Channel %s not configured for device %s", split[1], self.ip)

                elif split[0] in ['REP', 'REPORT']:
                    self.raw[split[1]] = ' '.join(split[2:])
            except Exception as e:
                logging.warning("Index Error(RX): %s - %s", data, e)


    def get_channels(self):
        channels = []
        for channel in self.channels:
            channels.append(channel.channel)
        return channels

    def get_all(self):
        ret = []
        for channel in self.get_channels():
            for s in self.BASECONST['getAll']:
                ret.append(s.format(channel))

        return ret

    def get_query_strings(self):
        ret = []
        for channel in self.get_channels():
            for s in self.BASECONST['query']:
                ret.append(s.format(channel))

        return ret


    def enable_metering(self, interval):
        if not self.writeQueue:
            self.writeQueue = asyncio.Queue()
        if self.type in ['qlxd', 'ulxd', 'axtd', 'p10t', 'slxd']:
            for i in self.get_channels():
                self.writeQueue.put_nowait('< SET {} METER_RATE {:05d} >'.format(i, int(interval * 1000)))
        elif self.type == 'uhfr':
            for i in self.get_channels():
                self.writeQueue.put_nowait('* METER {} ALL {:03d} *'.format(i, int(interval/30 * 1000)))

    def disable_metering(self):
        if not self.writeQueue:
            self.writeQueue = asyncio.Queue()
        for i in self.get_channels():
            self.writeQueue.put_nowait(self.BASECONST['meter_stop'].format(i))

    def net_json(self):
        ch_data = []
        for channel in self.channels:
            data = channel.ch_json()
            if self.rx_com_status == 'DISCONNECTED':
                data['status'] = 'RX_COM_ERROR'
            ch_data.append(data)
        data = {
            'ip': self.ip, 'type': self.type, 'status': self.rx_com_status,
            'raw': self.raw, 'tx': ch_data
        }
        return data
