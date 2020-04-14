# ns0 - Container DNS

## Examples

```bash
$ make
Some available commands:
 * run          - Run code.
 * test         - Run unit tests and test coverage.
 * doc          - Document code (pydoc).
 * clean        - Cleanup (e.g. pyc files).
 * code-style   - Check code style (pycodestyle).
 * code-lint    - Check code lints (pyflakes, pyline).
 * code-count   - Count code lines (cloc).
 * deps-install - Install dependencies (see requirements.txt).
 * deps-update  - Update dependencies (via pur).
 * feedback     - Create a GitHub issue.
```

```bash
$ make test
[D 180728 04:10:10 hello:23] <function print_message at 0x107867aa0>
Hello world!
[I 180728 04:10:10 hello:47] []
.
----------------------------------------------------------------------
Ran 1 test in 0.001s

OK
Name                  Stmts   Miss  Cover
-----------------------------------------
src/__init__.py           0      0   100%
src/hello.py             26      0   100%
tests/__init__.py         0      0   100%
tests/test_hello.py      12      0   100%
-----------------------------------------
TOTAL                    38      0   100%
```

## Get Started

### Run ns0

`docker run -v /var/run/docker.sock:/var/run/docker.sock registry.gitlab.com/peter.saarland/ns0:latest`

Environment-Variables:

* everything Lexicon supports
* ...

To instruct `ns0` to handle DNS for a container, add these labels to the container or service:

`ns0.host=sub.domain.tld.com`

## Development

* make sure `poetry` is installed
* git clone + cd to project directory
* `poetry shell`
* `code .`
* `poetry install`
