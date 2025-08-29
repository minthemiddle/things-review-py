You add dependencies according to PEP 723 directly in the header of a SCRIPT.py (after /// script)
You also add Python shebang so that script can be run alone

```
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
# ]
# ///
```

You can also add packages with `uv add --script SCRIPT.py httpx`
(This does the same as adding them directly in the header).

You always run the script with `uv run SCRIPT.py`.
You use `click` for CLI commands.
Use `option` with short, longhand and typing, e.g. `@click.option('-t', '--times', type=int)`
If dealing with transforming input files (e.g. `list.csv`), always write extra output files with `_out` pattern (`list_out.csv`)

You use `rich` library for user-friendly CLI UI.
You are an expert in UX for command-line.

You write in-file detailed comments about the "Why?" and "What's the result?" that a thing (e.g. function) does.

You use `python-dotenv` library for envs.