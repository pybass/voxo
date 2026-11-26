# Architecture

How the code of voxo is written: the rules that guide a change. What voxo does is in the
[README](../README.md).

## Shape

voxo is a pipeline: sound comes in, is cut into phrases, and a model turns each into text. It has no
database and no users, and its parts depend on each other in one direction. So the code is one object
with flat modules beside it. It has no services, no registry of features, and no folder per feature.
A design with those fits an app with a database and features that call each other; revisit this shape
when voxo gets one.

## Core

- `core/` is the whole app without an interface. It knows nothing of HTTP and nothing of a terminal.
- `Core` is the API of the whole app: one object, and every operation is a method of it.
- A client builds a `Core` and calls its methods. From `core/` it imports only `Core`, the types its
  methods return, and the errors. It never imports a module that stands beside `Core`.
- Imports go one way: a client imports `core/`, never the reverse.
- Building a `Core` starts no work. Only the server calls `start`, which locks the data dir until the
  process exits; a second server on the same data is refused. Any other client builds a `Core` and
  uses it as it is.
- Core never prints. What a client shows while a method works, such as the progress of a download,
  the method gives through a function the client passes in.
- Core raises its own errors, with a message written for the user. Each client translates them.

## Modules beside Core

- Each module in `core/` beside `Core` is one step of the pipeline or one concern.
- Such a module never sees `Core`. It gets plain values as arguments, such as a path or the samples
  of a sound, so it works without the app. `Core` builds what it needs from these modules and holds it.
- A file or folder in the data dir has one owner: the module that reads and writes it. No other
  module knows its name or its format.
- Only the code that runs a model or finds the pauses in a sound imports the library that does it. A
  second library gets a module of its own.
- A module that outgrows one file becomes a folder.

## Clients

- The command line and the web app are thin clients: each parses its input, calls `Core`, and shapes
  the answer. No rule of the app lives in a client.
- Only `web/` imports the web framework. Only the command line writes to the terminal.
- The web app translates the errors of core into HTTP codes in one place. A route catches no error by
  default.
- A command builds its own `Core` on the data dir it was given. A command other than the server works
  while the server runs.
