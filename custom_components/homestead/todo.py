"""The to-do list of a garden: generated tasks and own items."""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomesteadConfigEntry
from .entity import HomesteadEntity, garden_device
from .garden import Garden

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomesteadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One to-do list per garden."""
    async_add_entities([GardenTodoList(entry.runtime_data)])


def _day(value: date | datetime | None) -> date | None:
    return value.date() if isinstance(value, datetime) else value


class GardenTodoList(HomesteadEntity, TodoListEntity):
    """Tasks of the coming days. Ticking a task moves its planting on."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, garden: Garden) -> None:
        """Attach to the garden device."""
        super().__init__(garden, "tasks", garden.entry.entry_id, garden_device(garden))

    @property
    def todo_items(self) -> list[TodoItem]:
        """Open tasks by due date, then completed ones."""
        tasks = sorted(
            self.garden.tasks(),
            key=lambda task: (
                task.completed is not None,
                task.due or date.max,
                task.summary,
            ),
        )
        return [
            TodoItem(
                uid=task.uid,
                summary=task.summary,
                due=task.due,
                description=task.description,
                status=TodoItemStatus.COMPLETED
                if task.completed
                else TodoItemStatus.NEEDS_ACTION,
                completed=task.completed,
            )
            for task in tasks
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an own item."""
        await self.garden.async_add_item(
            item.summary or "", _day(item.due), item.description
        )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Tick or untick a task, or change an own item."""
        assert item.uid
        completed = item.status == TodoItemStatus.COMPLETED
        if not self.garden.is_generated(item.uid):
            await self.garden.async_update_item(
                item.uid,
                item.summary or "",
                _day(item.due),
                item.description,
                completed,
            )
        elif completed:
            await self.garden.async_complete_task(item.uid)
        else:
            await self.garden.async_reopen_task(item.uid)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Hide tasks or delete own items."""
        await self.garden.async_dismiss_tasks(uids)
