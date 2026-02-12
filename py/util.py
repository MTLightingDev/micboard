from typing import Union

def TVLookup(frequency: Union[str, float, int]) -> int:
    f = float(frequency)
    return int((f - 470) / 6 + 14)
