# Python Coding Rules

- Keep imports at the top of each module.
- Add type annotations and a docstring to every function and method.
- Prefer dataclasses for data models, but do not force them where they are unsuitable.
- Class-based UI components are acceptable and preferred where they provide clear ownership and lifecycle management.
- Do not install packages or modify the current environment. The user will create a separate application environment.
- Tests may be run only when they use the Python standard library and require no external package dependencies.
