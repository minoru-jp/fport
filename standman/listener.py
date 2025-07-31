
from typing import Protocol


class Listener(Protocol):
    def listen(self, tag: str, *args, **kwargs) -> None:
        ...

