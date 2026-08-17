# Engineering Record Governance

Design documents, implementation plans, and engineering records in the CADiPy public repository are treated as public material. They may explain architecture decisions, verification evidence, and maintenance constraints, but must not contain:

- temporary agent scratch notes or unedited reasoning;
- user directories, private paths, serial numbers, license credentials, tokens, passwords, or debug dumps;
- unrelated local machine information;
- unaudited binaries, generated output, or external product history.

Designs and plans in `docs/superpowers/` are public engineering history. `docs/development/` contains only curated, public, and maintainable engineering evidence. Temporary internal material must not be committed.
