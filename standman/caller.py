
import inspect
from pathlib import Path
from types import CodeType, FrameType
from typing import Any, Callable

def get_nth_caller_frame(base_frame: FrameType | None, *, back: int) -> FrameType:
    if base_frame is None:
        raise RuntimeError("Callee frame is None")
    frame = base_frame
    for _ in range(back):
        try:
            frame = frame.f_back # type: ignore None.f_back raises AttributeError
        except AttributeError as e:
            if frame is None:
                raise RuntimeError("Cannot inspect caller frame")
            raise e
    assert frame is not None
    return frame

def get_caller_location(callee_frame: FrameType | None) -> Path:
    caller_frame = get_nth_caller_frame(callee_frame, back = 1)
    caller_file = caller_frame.f_code.co_filename
    return Path(caller_file).resolve(strict = True)

def get_caller_code(callee_frame: FrameType | None) -> CodeType:
    if callee_frame is None:
        raise RuntimeError("Callee frame is None")
    caller_frame = get_nth_caller_frame(callee_frame, back = 1)
    return caller_frame.f_code

def get_callable_location(callable_: Callable[..., Any]) -> Path:
    source_file = inspect.getsourcefile(callable_)
    path = Path(source_file).resolve(strict=True) # type: ignore Path(None) raises TypeError
    assert source_file is not None
    assert path is not None
    return path

def check_in_scope(base: Path, target: Path):
    if target == base:
        return
    if target.is_relative_to(base):
        return
    raise PermissionError(f"Session request denied: Target is outside of base. (base = {base}; target ={target})")