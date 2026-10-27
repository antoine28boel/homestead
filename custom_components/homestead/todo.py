"""The garden's to-do list: generated tasks and own items."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import HomesteadError
from .const import DOMAIN
from .coordinator import HomesteadConfigEntry, HomesteadCoordinator
from .entity import HomesteadEntity, garden_device

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One to-do list per garden."""
    async_add_entities([GardenTodoList(entry.runtime_data)])


def _day(value: date | datetime | None) -> str | None:
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat() if value else None


def _item(task: dict[str, Any]) -> TodoItem:
    completed = dt_util.parse_datetime(task["completed"]) if task["completed"] else None
    return TodoItem(
        uid=task["uid"],
        summary=task["summary"],
        due=date.fromisoformat(task["due"]) if task["due"] else None,
        description=task["description"],
        status=TodoItemStatus.COMPLETED if completed else TodoItemStatus.NEEDS_ACTION,
        completed=completed,
    )


class GardenTodoList(HomesteadEntity, TodoListEntity):
    """Tasks of the coming days. Ticking a task moves its planting on."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: HomesteadCoordinator) -> None:
        """Attach to the garden device."""
        super().__init__(
            coordinator,
            "tasks",
            coordinator.data["instance_id"],
            garden_device(coordinator),
        )

    @property
    def todo_items(self) -> list[TodoItem]:
        """Tasks in the server's order: open by due date, then completed."""
        return [_item(task) for task in self.coordinator.data["tasks"]]

    def _generated(self, uid: str) -> bool:
        return any(
            task["uid"] == uid and task["generated"]
            for task in self.coordinator.data["tasks"]
        )

    async def _call(self, method: str, *args: Any) -> None:
        try:
            await getattr(self.coordinator.client, method)(*args)
        except HomesteadError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="server_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an own item."""
        await self._call(
            "create_task",
            {
                "summary": item.summary,
                "due": _day(item.due),
                "description": item.description,
            },
        )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Tick or untick a task, or change an own item."""
        assert item.uid
        completed = item.status == TodoItemStatus.COMPLETED
        if self._generated(item.uid):
            await self._call("update_task", item.uid, {"completed": completed})
            return
        await self._call(
            "update_task",
            item.uid,
            {
                "summary": item.summary,
                "due": _day(item.due),
                "description": item.description,
                "completed": completed,
            },
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete own items, hide generated tasks."""
        for uid in uids:
            await self._call("delete_task", uid)
