from typing import Generic, TypeVar
from datetime import datetime

T = TypeVar("T")


class CachedItem(Generic[T]):
    """
    Holds an item with type `T`, but locks it behind a bunch of different
    checks to make sure that the value actually still needs to be cached.
    """

    item: T
    expires_at: datetime | None

    def __init__(self, item: T, *, expires_at: datetime | None = None) -> None:
        super().__init__()
        self.item = item
        self.expires_at = expires_at

    def is_valid(self) -> bool:
        return not any([self.has_expired()])

    def has_expired(self) -> bool:
        if self.expires_at is None:
            return False

        return self.expires_at >= datetime.now()


class Cache(Generic[T]):
    """
    A very overcomplicated cache thing that caches an item `T` with
    additional validation checks.
    """

    cached_items: dict[str, CachedItem[T]]

    def __init__(self) -> None:
        self.cached_items = {}

    def add(self, key: str, item: T, *, expires_at: datetime | None = None) -> None:
        self.cached_items[key] = CachedItem(item, expires_at=expires_at)

    def get(self, key: str) -> T | None:
        tmp = self.cached_items.get(key, None)

        if not tmp:
            return None

        if not tmp.is_valid():
            return tmp.item
        else:
            del self.cached_items[key]

        return None

    def clean(self) -> None:
        for k, v in self.cached_items.items():
            if not v.is_valid():
                del self.cached_items[k]

    def remove(self, key : str) -> None:
        if key in self.cached_items:
            del self.cached_items[key]


__all__ = ["Cache", "CachedItem"]
