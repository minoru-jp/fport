"""
Protocols for callback functions in standman.

Defines typing contracts for senders and listeners used
in Port and Session communication.
"""

from typing import Protocol


class SendFunction(Protocol):
    def __call__(self, tag: str, *args, **kwargs) -> None:
        """A callable used by implementation side to send messages.

        Args:
            tag (str): Identifier for the message.
            *args: Arbitrary positional arguments for message data.
            **kwargs: Arbitrary keyword arguments for message data.
        """

class ListenFunction(Protocol):
    def __call__(self, tag: str, *args, **kwargs) -> None:
        """A callable used by receiver side to handle incoming messages.

        Args:
            tag (str): Identifier for the message.
            *args: Arbitrary positional arguments passed from sender.
            **kwargs: Arbitrary keyword arguments passed from sender.
        """

