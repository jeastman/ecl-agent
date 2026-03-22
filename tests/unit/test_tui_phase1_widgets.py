from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.compat import _TEXTUAL_IMPORT_ERROR
from apps.tui.local_agent_tui.store.app_state import AppState
from apps.tui.local_agent_tui.store.selectors import (
    PlanViewModel,
    TimelineEventViewModel,
    TimelineGroupViewModel,
    TodoItemViewModel,
    TodoPanelViewModel,
)


@unittest.skipIf(_TEXTUAL_IMPORT_ERROR is not None, "textual is not installed")
class Phase1WidgetDirtyCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_view_skips_repeated_identical_model(self) -> None:
        from textual.app import App, ComposeResult

        from apps.tui.local_agent_tui.widgets.plan_view import PlanViewWidget

        class TestApp(App[None]):
            def compose(self) -> ComposeResult:
                yield PlanViewWidget(id="plan")

        app = TestApp()
        async with app.run_test(size=(100, 24)):
            widget = app.query_one(PlanViewWidget)
            call_count = 0
            original_update = widget.update

            def counted_update(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return original_update(*args, **kwargs)

            widget.update = counted_update  # type: ignore[method-assign]
            model = PlanViewModel(current_phase="executing", current_step="Write tests", recent_updates=[])

            widget.update_plan(model)
            widget.update_plan(model)

            self.assertEqual(call_count, 1)

    async def test_todo_panel_skips_repeated_identical_model(self) -> None:
        from textual.app import App, ComposeResult

        from apps.tui.local_agent_tui.widgets.task_detail_panels import TodoPanelWidget

        class TestApp(App[None]):
            def compose(self) -> ComposeResult:
                yield TodoPanelWidget(id="todos")

        app = TestApp()
        async with app.run_test(size=(100, 24)):
            widget = app.query_one(TodoPanelWidget)
            call_count = 0
            original_update = widget.update

            def counted_update(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return original_update(*args, **kwargs)

            widget.update = counted_update  # type: ignore[method-assign]
            model = TodoPanelViewModel(
                items=[
                    TodoItemViewModel(
                        content="Render panel",
                        status="in_progress",
                        status_label="In Progress",
                        status_icon="◉",
                        is_active=True,
                    )
                ],
                pending_count=0,
                in_progress_count=1,
                completed_count=0,
            )

            widget.update_todos(model)
            widget.update_todos(model)

            self.assertEqual(call_count, 1)

    async def test_status_bar_skips_repeated_identical_context_state(self) -> None:
        from textual.app import App, ComposeResult

        from apps.tui.local_agent_tui.widgets.status_bar import StatusBar

        class TestApp(App[None]):
            def compose(self) -> ComposeResult:
                yield StatusBar(id="status")

        app = TestApp()
        async with app.run_test(size=(100, 24)):
            widget = app.query_one(StatusBar)
            context_bar = widget.query_one("#context-bar")
            call_count = 0
            original_update = context_bar.update

            def counted_update(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return original_update(*args, **kwargs)

            context_bar.update = counted_update  # type: ignore[method-assign]
            state = AppState(connection_status="connected")

            widget.update_from_state(state)
            widget.update_from_state(state)

            self.assertEqual(call_count, 1)

    async def test_event_timeline_skips_repeated_identical_body_model(self) -> None:
        from textual.app import App, ComposeResult

        from apps.tui.local_agent_tui.widgets.event_timeline import EventTimelineWidget

        class TestApp(App[None]):
            def compose(self) -> ComposeResult:
                yield EventTimelineWidget(id="timeline")

        app = TestApp()
        async with app.run_test(size=(100, 24)):
            widget = app.query_one(EventTimelineWidget)
            body = widget.query_one("#task-detail-timeline-body")
            call_count = 0
            original_update = body.update

            def counted_update(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return original_update(*args, **kwargs)

            body.update = counted_update  # type: ignore[method-assign]
            model = TimelineGroupViewModel(
                events=[
                    TimelineEventViewModel(
                        timestamp="2026-03-12T00:00:00Z",
                        timestamp_display="00:00",
                        event_type="tool.called",
                        severity_label="INFO",
                        summary="run command",
                        severity="info",
                        detail_lines=[],
                        repeat_count=1,
                        source_label="executor",
                        show_priority_highlight=False,
                        priority_label=None,
                    )
                ],
                filter_label="All",
                search_query="",
            )

            widget.update_timeline(model)
            widget.update_timeline(model)

            self.assertEqual(call_count, 1)
