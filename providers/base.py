from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List


class SearchResult:
    def __init__(self,
                 id: str,
                 title: str,
                 subtitle: str,
                 icon: str,
                 score: float,
                 category: str,
                 provider: str,
                 preview_data: Dict[str, Any] = None,
                 action_execute: Callable = None,
                 action_copy: Callable = None,
                 action_open_location: Callable = None,
                 action_delete: Callable = None):
        self.id = id
        self.title = title
        self.subtitle = subtitle
        self.icon = icon
        self.score = score
        self.category = category
        self.provider = provider
        self.preview_data = preview_data or {}

        # Actions
        self._action_execute = action_execute
        self._action_copy = action_copy
        self._action_open_location = action_open_location
        self._action_delete = action_delete

    def execute(self):
        if self._action_execute:
            self._action_execute()

    def copy_value(self):
        if self._action_copy:
            self._action_copy()

    def open_location(self):
        if self._action_open_location:
            self._action_open_location()

    def delete(self):
        if self._action_delete:
            self._action_delete()

class BaseProvider(ABC):
    def __init__(self, history_manager=None):
        self.history_manager = history_manager

    @abstractmethod
    def search(self, query: str, limit: int = 10, category_filter: str = None) -> List[SearchResult]:
        """
        Returns a list of SearchResult data objects.
        Should respect a cancellation token if passed (optional, for future deep async).
        """
        pass
