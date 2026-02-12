import time
import logging
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from networkdevice import ShureNetworkDevice

from device_config import BASE_CONST
from channel import ChannelDevice, data_update_list, chart_update_list

class IEM(ChannelDevice):
    def __init__(self, rx: 'ShureNetworkDevice', cfg: Dict[str, Any]) -> None:
        super().__init__(rx, cfg)
        self.audio_level_l = 0
        self.audio_level_r = 0

    def set_audio_level(self, audio_level: str, side: str) -> None:
        audio_level = int(audio_level)
        if audio_level < 10272:
            audio_level = 0
        elif 10272 <= audio_level < 23728:
            audio_level = 10
        elif 23728 <= audio_level < 85488:
            audio_level = 20
        elif 85488 <= audio_level < 246260:
            audio_level = 30
        elif 246260 <= audio_level < 641928:
            audio_level = 40
        elif 641928 <= audio_level < 1588744:
            audio_level = 50
        elif 1588744 <= audio_level < 2157767:
            audio_level = 60
        elif 2157767 <= audio_level < 2502970:
            audio_level = 70
        elif 2502970 <= audio_level:
            audio_level = 80

        if side == 'LEFT':
            self.audio_level_l = audio_level
        elif side == 'RIGHT':
            self.audio_level_r = audio_level

    def parse_report(self, split: List[str]) -> None:
        if split[2] == self.CHCONST['name']:
            self.set_chan_name_raw(' '.join(split[3:]))
        elif split[2] == self.CHCONST['frequency']:
            self.set_frequency(split[3])
        elif split[2] == self.CHCONST['audio_level_l']:
            self.set_audio_level(split[3], 'LEFT')
        elif split[2] == self.CHCONST['audio_level_r']:
            self.set_audio_level(split[3], 'RIGHT')
            chart_update_list.append(self.chart_json())

    def parse_sample(self, split: List[str]) -> None:
        pass

    def ch_state(self) -> str:
        if self.rx.rx_com_status in ['DISCONNECTED', 'CONNECTING']:
            return 'RX_COM_ERROR'

        if self.rx.rx_com_status == 'CONNECTED':
            return 'UNASSIGNED'

        return 'TX_COM_ERROR'

    def chart_json(self) -> Dict[str, Any]:
        data = super().chart_json()
        data.update({
            'audio_level_l': self.audio_level_l,
            'audio_level_r': self.audio_level_r,
        })
        return data

    def ch_json(self) -> Dict[str, Any]:
        data = super().ch_json()
        data.update({
            'status': self.ch_state(),
            'audio_level_l': self.audio_level_l,
            'audio_level_r': self.audio_level_r,
        })
        return data
