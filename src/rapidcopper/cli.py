import ast
import importlib.util
import os
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any
from xml.dom import NotFoundErr

import typer

app = typer.Typer()


@dataclass
class Pipe:
    name: str
    description: str
    location: str

    @property
    def path(self) -> Path:
        return Path(self.description)

    def display(self):
        return f"action:\t{self.name} - {self.description}\n\t\t{self.location}"

    def run(self, arg: str) -> Callable[[str], Any]:
        spec = importlib.util.spec_from_file_location(
            f"action.{self.name}", self.location
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore

        return module.run(arg)


@dataclass
class Action:
    name: str
    description: str
    location: str

    @property
    def path(self) -> Path:
        return Path(self.description)

    def display(self):
        return f"action:\t{self.name} - {self.description}\n\t\t{self.location}"

    def run(self, *args: tuple[str, ...]) -> Callable[..., Any]:
        spec = importlib.util.spec_from_file_location(
            f"action.{self.name}", self.location
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore

        return module.run(*args)


@dataclass
class App:
    name: str
    description: str
    location: str

    @property
    def path(self) -> Path:
        return Path(self.description)

    def display(self):
        return f"app:\t\t{self.name} - {self.description}\n\t\t{self.location}"

    def run(self) -> None:
        subprocess.run(["gtk-launch", Path(self.location).name])


@app.command()
def rebuild_index() -> None:
    config_path = Path.home() / ".config" / "rapidcopper"
    plugin_path = config_path / "plugins"
    index_path = config_path / "index.sqlite"

    os.makedirs(plugin_path, exist_ok=True)

    index_path.unlink(missing_ok=True)

    con = sqlite3.connect(index_path)
    cursor = con.cursor()

    index_setup(cursor)

    index_populate_application(cursor)
    index_populate_action(cursor, plugin_path)
    index_populate_pipe(cursor, plugin_path)

    con.commit()


@app.command()
def do(args: list[str]) -> None:
    current = None
    for idx, group in enumerate(do_break_pipes(args)):
        if idx == 0:
            # first command, only query actions and apps
            candidates = query_begin(group[0], group[1:])

            if len(candidates) == 1 and len(group) == 1:
                if isinstance(candidates[0], App):
                    candidates[0].run()
                else:
                    arguments = typer.prompt("Enter arguments: ")
                    current = candidates[0].run(*(arguments.split(" ")))

            elif len(candidates) == 1:
                current = candidates[0].run(*group[1:])

            elif candidates and len(group) == 1:
                # show all the candidates
                show_candidates(candidates)

                choice = int(typer.prompt("Enter choice: "))
                if isinstance(candidates[choice], App):
                    candidates[choice].run()
                else:
                    arguments = typer.prompt("Enter arguments: ")
                    current = candidates[choice].run(*(arguments.split(" ")))

            elif candidates:
                show_candidates(candidates)

                choice = int(typer.prompt("Enter choice: "))

                current = candidates[choice].run(*group[1:])

            else:
                raise NotFoundErr("No suitable action is found")

        elif current:
            candidates = query_pipe(group[0])

            if len(candidates) == 1:
                current = candidates[0].run(current)  # type: ignore
            else:
                show_candidates(candidates)

                choice = int(typer.prompt("Enter choice: "))

                current = candidates[choice].run(current)


def show_candidates(candidates: list[App | Action | Pipe]) -> None:
    for idx, candidate in enumerate(candidates):
        print(idx, candidate.display())


def query_pipe(command: str) -> list[Pipe]:
    result = []

    config_path = Path.home() / ".config" / "rapidcopper"
    index_path = config_path / "index.sqlite"

    con = sqlite3.connect(index_path)
    cursor = con.cursor()
    cursor.row_factory = lambda _cursor, row: Pipe(*row)
    result.extend(
        cursor.execute(
            "select name, description, location from pipe where name LIKE ?",
            (command_expand_like(command),),
        ).fetchall()
    )

    return result


def query_begin(command: str, args: list[str]) -> list[App | Action]:
    result = []

    config_path = Path.home() / ".config" / "rapidcopper"
    index_path = config_path / "index.sqlite"

    con = sqlite3.connect(index_path)
    cursor = con.cursor()

    if not args:
        cursor.row_factory = lambda _cursor, row: App(*row)

        result.extend(
            cursor.execute(
                "select name, description, location from application where name LIKE ?",
                (command_expand_like(command),),
            ).fetchall()
        )

    cursor.row_factory = lambda _cursor, row: Action(*row)
    result.extend(
        cursor.execute(
            "select name, description, location from action where name LIKE ?",
            (command_expand_like(command),),
        ).fetchall()
    )

    return result


def command_expand_like(command: str) -> str:
    result = "".join(f"{char}%" for char in list(command))

    return f"%{result}"


def do_break_pipes(args: list[str]):
    groups, current = [], []

    # group by pipe
    for arg in args:
        if arg == "|":
            groups.append(current)
            current = []
        else:
            current.append(arg)

    if current:
        groups.append(current)

    return groups


def index_populate_action(cursor: sqlite3.Cursor, plugin_path: Path) -> None:
    for entry in chain.from_iterable(
        os.scandir(path) for path in (Path(__file__).parent / "plugins", plugin_path)
    ):
        if not (entry.name.startswith("action_") and entry.name.endswith(".py")):
            continue

        with open(entry.path, "r") as file:
            description = ast.literal_eval(file.readline())
            cursor.execute(
                """
                INSERT INTO action (name, description, location) VALUES (?, ?, ?)
                """,
                (
                    entry.name.lower().split(".")[0].split("action_")[-1],
                    description,
                    entry.path,
                ),
            )


def index_populate_pipe(cursor: sqlite3.Cursor, plugin_path: Path) -> None:
    for entry in chain.from_iterable(
        os.scandir(path) for path in (Path(__file__).parent / "plugins", plugin_path)
    ):
        if not (entry.name.startswith("pipe_") and entry.name.endswith(".py")):
            continue

        with open(entry.path, "r") as file:
            description = ast.literal_eval(file.readline())

            cursor.execute(
                """
                INSERT INTO pipe (name, description, location) VALUES (?, ?, ?)
                """,
                (
                    entry.name.lower().split(".")[0].split("pipe_")[-1],
                    description,
                    entry.path,
                ),
            )


def index_populate_application(cursor: sqlite3.Cursor) -> None:
    for entry in chain.from_iterable(
        os.scandir(path)
        for path in (
            Path("/usr/share/applications"),
            Path.home() / ".local" / "share" / "applications",
            Path.home() / ".nix-profile" / "share" / "application",
        )
        if path.exists()
    ):
        if not check_is_desktop_file(entry):
            continue

        with open(entry.path, "r") as desktop:
            name_def = next(
                line for line in desktop.readlines() if line.lower().startswith("name=")
            ).strip()
            desktop.seek(0)
            try:
                description = next(
                    line
                    for line in desktop.readlines()
                    if line.lower().startswith("comment=")
                ).strip()
            except StopIteration:
                description = ""

            cursor.execute(
                """
                INSERT INTO application (name, description, location) VALUES (?, ?, ?)
                """,
                (
                    entry.path,
                    description[description.index("=") + 1 :] if description else "",
                    name_def[name_def.index("=") + 1 :],
                ),
            )


def index_setup(cursor):
    cursor.execute(
        """
        CREATE TABLE application (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            location BLOB NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE action (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE pipe (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL
        );
        """
    )


def check_is_desktop_file(file: os.DirEntry) -> bool:
    return file.name.split(".")[-1].lower() == "desktop"


if __name__ == "__main__":
    app()