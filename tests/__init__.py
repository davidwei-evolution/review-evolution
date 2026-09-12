"""Test package marker (2026-09-12, U8).

Without this file `python -m unittest discover -s <abs>/tests -t <abs>` fails with
"Start directory is not importable", which users reasonably misread as a broken test
environment. With it, the suite can be discovered both from the skill root
(`discover -s tests -t tests`) and from an outside working directory.
"""
