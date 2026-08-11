# LagScope Python Code Guide

This guide separates the Python language from code written specifically for
LagScope. It is intended for learning, code review, and interview preparation.

## The four categories

- **Project code**: names and behaviour written for LagScope, such as
  `ping_once()` and `ProbeResult`.
- **Python built-in**: available without an import, such as `print()`, `int()`,
  `str()`, `OSError`, and the types `str`, `int`, and `bool`.
- **Built-in type method**: behaviour attached to a built-in object, such as
  `some_text.lower()`, `strip()`, and `splitlines()`.
- **Standard library**: supplied with Python but imported from a module, such
  as `subprocess.run()`, `re.search()`, and `argparse.ArgumentParser`.

## Features used by LagScope

| Feature | Category | What it does here | Official documentation topic |
|---|---|---|---|
| `@dataclass` | Standard library | Generates the constructor used to create `ProbeResult` objects. | `dataclasses` |
| `str`, `int`, `bool` | Python built-ins | Represent text, whole numbers, and true/false values. They are also used as type hints. | Built-in types |
| `None` | Python built-in value | Represents the deliberate absence of a value, such as no latency after failure. | The `None` object |
| `list` syntax: `[...]` | Python syntax/built-in type | Keeps command pieces and failure messages in order. | Lists |
| `for` | Python syntax | Processes list items or output lines one at a time. | `for` statements |
| `if` / `else` | Python syntax | Selects a path based on a true/false condition. | `if` statements |
| `in` | Python operator | Checks whether one string occurs inside another string. | Membership tests |
| `or` | Python operator | Produces `True` when either condition is true. | Boolean operations |
| `return` | Python syntax | Ends the current function and sends a value back to its caller. | `return` statements |
| `text.lower()` | Built-in `str` method | Returns a lowercase copy for case-insensitive comparisons. | String methods: `str.lower` |
| `text.strip()` | Built-in `str` method | Removes leading and trailing whitespace and newline characters. | String methods: `str.strip` |
| `text.splitlines()` | Built-in `str` method | Splits multiline output into individual line strings. | String methods: `str.splitlines` |
| `str(value)` | Python built-in | Converts a value to text; used for command arguments and errors. | `str` |
| `int(text)` | Python built-in | Converts captured latency text such as `"6"` to the integer `6`. | `int` |
| `print(text)` | Python built-in | Writes the final report to standard output. | `print` |
| f-string: `f"{value}"` | Python syntax | Inserts a value into formatted output text. | Formatted string literals |
| `try` / `except` | Python syntax | Handles anticipated errors without crashing with a traceback. | Errors and exceptions |
| `OSError` | Python built-in exception | Represents an operating-system failure, such as inability to start a program. | Built-in exceptions: `OSError` |
| `datetime.now(timezone.utc)` | Standard library | Gets the current time with an explicit UTC timezone. | `datetime` |
| `.isoformat()` | `datetime` method | Converts the timestamp object to standard, readable text. | `datetime.isoformat` |
| `subprocess.run()` | Standard library | Runs `ping.exe`, waits for completion, and returns a `CompletedProcess`. | `subprocess.run` |
| `capture_output=True` | `subprocess.run` option | Saves standard output and standard error for LagScope to inspect. | `subprocess.run` |
| `text=True` | `subprocess.run` option | Returns captured output as strings instead of bytes. | `subprocess.run` |
| `timeout=...` | `subprocess.run` option | Limits how long Python waits for the complete child process. | `subprocess.run` timeout |
| `check=False` | `subprocess.run` option | Returns non-zero process results rather than raising `CalledProcessError`. | `subprocess.run` check |
| `subprocess.TimeoutExpired` | Standard library exception | Indicates that the complete child process exceeded Python's timeout. | `subprocess.TimeoutExpired` |
| `.stdout` / `.stderr` | `CompletedProcess` attributes | Hold captured normal output and error output. | `subprocess.CompletedProcess` |
| `.returncode` | `CompletedProcess` attribute | Holds the integer exit status returned by `ping.exe`. | `subprocess.CompletedProcess` |
| raw string: `r"..."` | Python syntax | Preserves backslashes so the regular expression receives `\d` unchanged. | Raw string literals |
| `re.search()` | Standard library | Searches the ping output for the first matching latency pattern. | `re.search` |
| `re.IGNORECASE` | Standard library option | Makes the regular-expression search ignore letter case. | Regular expression flags |
| `match.group(1)` | Standard library `Match` method | Returns the text captured by the first parentheses in the pattern. | Regular expression match objects |
| `argparse.ArgumentParser()` | Standard library | Creates a parser for command-line options. | `argparse.ArgumentParser` |
| `parser.add_argument()` | Standard library method | Defines an option, its data type, default, and help text. | `ArgumentParser.add_argument` |
| `parser.parse_args()` | Standard library method | Reads PowerShell arguments and returns a `Namespace`. | `ArgumentParser.parse_args` |
| `parser.error()` | Standard library method | Prints an argument error and terminates with usage information. | `ArgumentParser.error` |
| `__name__ == "__main__"` | Python runtime convention | Runs `main()` only when this file is executed directly. | Python `__main__` |

## The regular expression

LagScope uses:

```python
latency_pattern = r"time[=<](\d+)ms"
```

It means:

```text
time     literal text
[=<]     exactly one character: = or <
(\d+)    capture one or more digits
ms       literal text
```

It matches both `time=6ms` and `time<1ms`. For `time=6ms`, capture group 1
contains `"6"`.

## Official references

- [Python built-in functions](https://docs.python.org/3/library/functions.html)
- [Python built-in types and string methods](https://docs.python.org/3/library/stdtypes.html)
- [Python `argparse`](https://docs.python.org/3/library/argparse.html)
- [Python `dataclasses`](https://docs.python.org/3/library/dataclasses.html)
- [Python `datetime`](https://docs.python.org/3/library/datetime.html)
- [Python regular expressions](https://docs.python.org/3/library/re.html)
- [Python `subprocess`](https://docs.python.org/3/library/subprocess.html)
- [Python errors and exceptions tutorial](https://docs.python.org/3/tutorial/errors.html)
- [Python formatted string literals](https://docs.python.org/3/tutorial/inputoutput.html#formatted-string-literals)

When searching manually, use the exact names in the final column of the table,
prefixed with `Python`. For example: `Python subprocess.run documentation`.
