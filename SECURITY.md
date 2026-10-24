# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's advisory form:
<https://github.com/hellpuffyt/sql-migrate-lint/security/advisories/new>

Please do not open a public issue for a vulnerability.

In scope, for example: the linter connecting to a database, executing SQL,
reading or writing files other than the inputs and `--output`, or a crafted
`.sql` file that makes it hang or exhaust memory.

A dangerous migration pattern that the linter misses (a false negative) is
a correctness bug rather than a vulnerability — please open a normal issue
with a minimal SQL example.

## Supported versions

Only the latest release on the default branch receives fixes.
