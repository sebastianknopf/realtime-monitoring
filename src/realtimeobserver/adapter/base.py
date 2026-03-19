from abc import ABC, abstractmethod

class BaseAdapter(ABC):

    def __init__(self, token: str|None, endpoint: str) -> None:
        self._token: str|None = token
        self._endpoint: str = endpoint

    @abstractmethod
    def process(self, stop_id: str, line_ids: list[str]|None) -> tuple[list[dict], str]:
        pass