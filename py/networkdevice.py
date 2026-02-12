import time
import queue
import socket
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
        self.writeQueue: queue.Queue = queue.Queue()
        self.f: Optional[socket.socket] = None
        self.socket_watchdog = int(time.monotonic())
        self.raw: Dict[str, Any] = defaultdict(dict)
        self.BASECONST: Dict[str, Any] = BASE_CONST[self.type]['base_const']

    def socket_connect(self) -> None:
        try:
            if BASE_CONST[self.type]['PROTOCOL'] == 'TCP':
                self.f = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #TCP
                self.f.settimeout(.2)
                self.f.connect((self.ip, PORT))


            elif BASE_CONST[self.type]['PROTOCOL'] == 'UDP':
                self.f = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #UDP

            self.set_rx_com_status('CONNECTING')
            self.enable_metering(.1)

            for string in self.get_all():
                self.writeQueue.put(string)
        except socket.error as e:
            self.set_rx_com_status('DISCONNECTED')

        self.socket_watchdog = int(time.monotonic())


    def socket_disconnect(self) -> None:
        if self.f:
            self.f.close()
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
                    ch.parse_raw_ch(data)

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
        if self.type in ['qlxd', 'ulxd', 'axtd', 'p10t']:
            for i in self.get_channels():
                self.writeQueue.put('< SET {} METER_RATE {:05d} >'.format(i, int(interval * 1000)))
        elif self.type == 'uhfr':
            for i in self.get_channels():
                self.writeQueue.put('* METER {} ALL {:03d} *'.format(i, int(interval/30 * 1000)))

    def disable_metering(self):
        for i in self.get_channels():
            self.writeQueue.put(self.BASECONST['meter_stop'].format(i))

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
