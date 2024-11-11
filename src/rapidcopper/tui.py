import asyncio
from dataclasses import dataclass
from typing import Any

from textual import events, log, on
from textual.app import App, ComposeResult
from textual.widgets import Input, Label, ListItem, ListView

from rapidcopper.cli import Action, Pipe, do_break_pipes, query_action_app, query_pipe
from rapidcopper.cli import App as Application


@dataclass
class Error:
    description: str

    def display(self) -> str:
        return self.description


class Main(App):
    # FIXME cache result
    # stack: dict[tuple[str, str | None], list[App | Action] | list[Pipe]]
    widget_result: ListView
    widget_query: Input

    candidates: list[Application | Action] | list[Pipe] | list[Error]
    result: Any

    def on_load(self):
        # FIXME cache result
        # self.stack = {}
        self.candidates = []
        self.result = None

    def compose(self) -> ComposeResult:
        self.widget_result = ListView(id="result", disabled=True)
        self.widget_query = Input(id="query")

        yield self.widget_query
        yield self.widget_result

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()

        elif event.key == "up":
            self.widget_result.action_cursor_up()

        elif event.key == "down":
            self.widget_result.action_cursor_down()

        elif event.key == "enter":
            self.widget_result.action_select_cursor()

    def tokenize(self, value: str) -> list[str]:
        result = value.replace("|", " | ").split()

        if result and result[-1] == "|":
            result.append("")

        return result

    @on(Input.Changed, "#query")
    async def query_changed(self, message: Input.Changed) -> None:
        previous = []
        result = None
        candidates = []

        for idx, group in enumerate(do_break_pipes(self.tokenize(message.value))):
            if idx == 0:
                candidates = query_action_app(*group)

                previous = group
                pass

            elif not candidates:
                candidates = [Error(description="No input specified")]
                break

            else:
                # execute previous command
                result = candidates[0].run(*previous[1:])

                candidates = query_pipe(group[0])

        self.candidates = candidates
        self.result = result

        await self.widget_result.clear()

        for candidate in candidates:
            await self.widget_result.append(ListItem(Label(candidate.display())))

        if candidates:
            self.widget_result.index = 0

    @on(ListView.Selected, "#result")
    def result_selected(self, message: ListView.Selected) -> None:
        selected = self.candidates[message.list_view.index or 0]
        log(selected)

        if isinstance(selected, Application):
            selected.run()

        elif isinstance(selected, Action):
            selected.run(*self.result)

        elif isinstance(selected, Pipe):
            selected.run(self.result)

        self.exit()

def main():
    app = Main()
    app.run()

if __name__ == "__main__":
    main()
elif __name__ == "rapidcopper.tui":
    app = Main()