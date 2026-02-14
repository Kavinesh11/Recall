"""CLI entry point: python -m recall"""

from recall.agents import recall

if __name__ == "__main__":
    recall.cli_app(stream=True)
