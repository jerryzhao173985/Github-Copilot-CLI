from setuptools import setup, find_packages

setup(
    name="copilot-cli",
    version="0.1.0",
    packages=find_packages(include=["copilot_cli", "copilot_cli.*"]),
    install_requires=[],
    entry_points={
        "console_scripts": [
            "copilot=copilot_cli.__main__:main",
        ],
    },
)