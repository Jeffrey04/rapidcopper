import ast
import importlib.util
import os
import pkgutil
import sqlite3
import subprocess
from collections.abc import Generator
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any
from xml.dom import NotFoundErr

import typer
from Levenshtein import distance

import rapidcopper.plugins

app = typer.Typer()


@dataclass
class Pipe:
    name: str
    description: str
    location: str
    is_builtin: bool

    @property
    def path(self) -> Path:
        return Path(self.description)

    def display(self):
        return f"action:\t{self.name} - {self.description}\n\t\t{self.location}"

    def run(self, arg: str) -> Any:
        module = None

        if self.is_builtin is False:
            spec = importlib.util.spec_from_file_location(
                f"action.{self.name}", self.location
            )
            module = importlib.util.module_from_spec(spec)  # type: ignore
            spec.loader.exec_module(module)  # type: ignore

        else:
            module = importlib.import_module(self.location)

        return module.run(arg)


@dataclass
class Action:
    name: str
    description: str
    location: str
    is_builtin: bool

    @property
    def path(self) -> Path:
        return Path(self.description)

    def display(self):
        return f"action:\t{self.name} - {self.description}\n\t\t{self.location}"

    def run(self, *args: tuple[str, ...]) -> Any:
        module = None

        if self.is_builtin is False:
            spec = importlib.util.spec_from_file_location(
                f"action.{self.name}", self.location
            )
            module = importlib.util.module_from_spec(spec)  # type: ignore
            spec.loader.exec_module(module)  # type: ignore

        else:
            module = importlib.import_module(self.location)

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
        subprocess.run(
            ["gtk-launch", Path(self.location).name], stderr=subprocess.DEVNULL
        )


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
            candidates = query_action_app(*group)

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


def show_candidates(candidates: list[App | Action] | list[Pipe]) -> None:
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
            """
            SELECT  name, description, location, is_builtin
            FROM    pipe
            WHERE name LIKE ?
            """,
            (command_expand_like(command),),
        ).fetchall()
    )

    return sorted(result, key=lambda incoming: distance(command, incoming.name))[:5]


def query_action_app(command: str, *args: str) -> list[App | Action]:
    result = []

    config_path = Path.home() / ".config" / "rapidcopper"
    index_path = config_path / "index.sqlite"

    con = sqlite3.connect(index_path)
    cursor = con.cursor()

    if not args:
        cursor.row_factory = lambda _cursor, row: App(*row)

        result.extend(
            cursor.execute(
                """
                SELECT  name, description, location
                FROM    application
                WHERE   name LIKE ?
                """,
                (command_expand_like(command),),
            ).fetchall()
        )

    cursor.row_factory = lambda _cursor, row: Action(*row)
    result.extend(
        cursor.execute(
            """
            SELECT  name, description, location, is_builtin
            FROM    action
            WHERE   name LIKE ?
            """,
            (command_expand_like(command),),
        ).fetchall()
    )

    return sorted(result, key=lambda incoming: distance(command, incoming.name))[:5]


def command_expand_like(command: str) -> str:
    return f"%{command}%"


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
    for entry in os.scandir(plugin_path):
        if not (entry.name.startswith("action_") and entry.name.endswith(".py")):
            continue

        with open(entry.path, "r") as file:
            description = ast.literal_eval(file.readline())
            cursor.execute(
                """
                INSERT INTO action (name, description, location, is_builtin) VALUES (?, ?, ?, ?)
                """,
                (
                    entry.name.lower().split(".")[0].split("action_")[-1],
                    description,
                    entry.path,
                    False,
                ),
            )

    for _finder, name, _ispkg in pkgutil.iter_modules(
        rapidcopper.plugins.__path__,  # type: ignore
        rapidcopper.plugins.__name__ + ".",  # type: ignore
    ):
        if name.split(".")[-1].startswith("action_"):
            cursor.execute(
                """
                INSERT
                INTO     action (name, description, location, is_builtin)
                VALUES   (?, ?, ?, ?)
                """,
                (
                    name.split(".")[-1].split("action_")[-1],
                    importlib.import_module(name).__doc__,
                    name,
                    True,
                ),
            )


def index_populate_pipe(cursor: sqlite3.Cursor, plugin_path: Path) -> None:
    for entry in os.scandir(plugin_path):
        if not (entry.name.startswith("pipe_") and entry.name.endswith(".py")):
            continue

        with open(entry.path, "r") as file:
            description = ast.literal_eval(file.readline())

            cursor.execute(
                """
                INSERT INTO pipe (name, description, location, is_builtin) VALUES (?, ?, ?, ?)
                """,
                (
                    entry.name.lower().split(".")[0].split("pipe_")[-1],
                    description,
                    entry.path,
                    False,
                ),
            )

    for _finder, name, _ispkg in pkgutil.iter_modules(
        rapidcopper.plugins.__path__,  # type: ignore
        rapidcopper.plugins.__name__ + ".",  # type: ignore
    ):
        if name.split(".")[-1].startswith("pipe_"):
            cursor.execute(
                """
                INSERT
                INTO     pipe (name, description, location, is_builtin)
                VALUES   (?, ?, ?, ?)
                """,
                (
                    name.split(".")[-1].split("pipe_")[-1],
                    importlib.import_module(name).__doc__,
                    name,
                    True,
                ),
            )


def desktop_file_get_directory() -> Generator[Path]:
    return (
        path / "applications"
        for path in chain(
            map(Path, os.environ["XDG_DATA_DIRS"].split(":")),
            (
                Path.home() / ".local" / "share",
                Path.home() / ".nix-profile" / "share",
            ),
        )
    )


def index_populate_application(cursor: sqlite3.Cursor) -> None:
    for entry in chain.from_iterable(
        map(os.scandir, filter(lambda d: d.exists(), desktop_file_get_directory()))
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
                    name_def[name_def.index("=") + 1 :],
                    description[description.index("=") + 1 :] if description else "",
                    entry.path,
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
            location TEXT NOT NULL,
            is_builtin BOOLEAN NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE pipe (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            is_builtin BOOLEAN NOT NULL
        );
        """
    )


def check_is_desktop_file(file: os.DirEntry) -> bool:
    return file.name.split(".")[-1].lower() == "desktop"


if __name__ == "__main__":
    app()
