from setuptools import setup, find_packages
import os

# Install the DSL package `puzzlespec` from the repo root.
# Legacy code remains in the tree but is not part of this installable package.

# Read the contents of your README file for long description
this_directory = os.path.abspath(os.path.dirname(__file__))
try:
    with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "A domain-specific language for logic puzzles"

setup(
    name="puzzlespec",
    version="0.1.0",
    author="Ross Daly",  # Replace with your name
    author_email="rdaly525@cs.stanford.edu",  # Replace with your email
    description="A domain-specific language for logic puzzles",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=find_packages(where="src", include=["puzzlespec", "puzzlespec.*"]),
    python_requires=">=3.10",
    install_requires=[
        "numpy",
        "hwtypes",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
            "black",
            "flake8",
            "mypy",
        ],
    },
)
