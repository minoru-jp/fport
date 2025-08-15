
from typing import Protocol


class SendFunction(Protocol):
    def __call__(self, tag: str, *args, **kwargs) -> None:
        ...

class ListenFunction(Protocol):
    def __call__(self, tag: str, *args, **kwargs) -> None:
        ...

