from __future__ import annotations

import functools
from typing import Any, ClassVar, TypedDict

from sentry.api.serializers import Serializer, register, serialize
from sentry.search.utils import convert_user_tag_to_query
from sentry.tagstore.base import TagKeyStatus


@functools.total_ordering
class TagType:
    _sort_key: ClassVar[str]
    __slots__: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return "<{}: {}>".format(
            type(self).__name__,
            ", ".join(f"{name}={getattr(self, name)!r}" for name in self.__slots__),
        )

    def __hash__(self) -> int:
        return hash(tuple(getattr(self, name) for name in self.__slots__))

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and all(
            getattr(self, name) == getattr(other, name) for name in self.__slots__
        )

    def __lt__(self, other: object) -> bool:
        return getattr(self, self._sort_key) < getattr(other, self._sort_key)

    def __getstate__(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}

    def __setstate__(self, state: dict[str, Any]) -> None:
        for name, value in state.items():
            setattr(self, name, value)


class TagKey(TagType):
    __slots__ = ("key", "values_seen", "status", "count", "top_values")
    _sort_key = "values_seen"

    def __init__(
        self, key, values_seen=None, status=TagKeyStatus.ACTIVE, count=None, top_values=None
    ):
        self.key = key
        self.values_seen = values_seen
        self.status = status
        self.count = count
        self.top_values = top_values

    def get_audit_log_data(self):
        return {"key": self.key}


class TagValue(TagType):
    __slots__ = ("key", "value", "times_seen", "first_seen", "last_seen")
    _sort_key = "value"

    def __init__(self, key, value, times_seen, first_seen, last_seen):
        self.key = key
        self.value = value
        self.times_seen = times_seen
        self.first_seen = first_seen
        self.last_seen = last_seen


class GroupTagKey(TagType):
    __slots__ = ("group_id", "key", "values_seen", "count", "top_values")
    _sort_key = "values_seen"

    def __init__(self, group_id, key, values_seen=None, count=None, top_values=None):
        self.group_id = group_id
        self.key = key
        self.values_seen = values_seen
        self.count = count
        self.top_values = top_values


class GroupTagValue(TagType):
    __slots__ = ("group_id", "key", "value", "times_seen", "first_seen", "last_seen")
    _sort_key = "value"

    def __init__(self, group_id, key, value, times_seen, first_seen, last_seen):
        self.group_id = group_id
        self.key = key
        self.value = value
        self.times_seen = times_seen
        self.first_seen = first_seen
        self.last_seen = last_seen


class TagKeySerializerResponseOptional(TypedDict, total=False):
    uniqueValues: int | None
    totalValues: int | None
    topValues: list[TagValueSerializerResponse] | None


class TagKeySerializerResponse(TagKeySerializerResponseOptional):
    key: str
    name: str


@register(GroupTagKey)
@register(TagKey)
class TagKeySerializer(Serializer):
    def serialize(self, obj, attrs, user, **kwargs) -> TagKeySerializerResponse:
        from sentry import tagstore

        output: TagKeySerializerResponse = {
            "key": tagstore.backend.get_standardized_key(obj.key),
            "name": tagstore.backend.get_tag_key_label(obj.key),
        }
        if obj.values_seen is not None:
            output["uniqueValues"] = obj.values_seen
        if obj.count is not None:
            output["totalValues"] = obj.count
        if obj.top_values is not None:
            output["topValues"] = serialize(obj.top_values, user)
        return output


class TagValueSerializerResponseOptional(TypedDict, total=False):
    query: str | None


class TagValueSerializerResponse(TagValueSerializerResponseOptional):
    key: str
    name: str
    value: str
    count: int
    lastSeen: str
    firstSeen: str


@register(GroupTagValue)
@register(TagValue)
class TagValueSerializer(Serializer):
    def serialize(self, obj, attrs, user, **kwargs) -> TagValueSerializerResponse:
        from sentry import tagstore

        key = tagstore.backend.get_standardized_key(obj.key)
        serialized: TagValueSerializerResponse = {
            "key": key,
            "name": tagstore.backend.get_tag_value_label(obj.key, obj.value),
            "value": obj.value,
            "count": obj.times_seen,
            "lastSeen": obj.last_seen,
            "firstSeen": obj.first_seen,
        }

        query = convert_user_tag_to_query(key, obj.value)
        if query:
            serialized["query"] = query

        return serialized
