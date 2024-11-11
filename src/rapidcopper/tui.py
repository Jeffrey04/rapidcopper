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
        self.widget_result = ListView(id="result")
        self.widget_query = Input(id="query")

        yield self.widget_query
        yield self.widget_result

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()

    @on(Input.Changed, "#query")
    def query_changed(self, message: Input.Changed) -> None:
        previous = []
        result = None
        candidates = []

        for idx, group in enumerate(do_break_pipes(message.value.split(" "))):
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

        self.widget_result.clear()
        for candidate in candidates:
            self.widget_result.append(ListItem(Label(candidate.display())))

    @on(ListView.Selected, "#result")
    def result_selected(self, message: ListView.Selected) -> None:
        selected = self.candidates[message.list_view.index or 0]

        if isinstance(selected, Application):
            selected.run()
        elif isinstance(selected, Action):
            selected.run(*self.result)
        elif isinstance(selected, Pipe):
            selected.run(self.result)

        self.exit()


if __name__ == "__main__":
    app = Main()
    app.run()
