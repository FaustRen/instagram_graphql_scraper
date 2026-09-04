"""Manual-free smoke checks live in tests/test_graphql.py.

Run the real browser flow with manual_integration.py so dynamic request values
are captured at runtime and never stored in this repository.
"""

from graphql import OPERATION_NAME


if __name__ == "__main__":
    print(f"Target operation: {OPERATION_NAME}")
