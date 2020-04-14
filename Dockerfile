FROM python:3-alpine
RUN apk update && \
  apk add \
  build-base \
  curl \
  git \
  libffi-dev \
  openssh-client \
  postgresql-dev

# Install Poetry & ensure it is in $PATH
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | POETRY_PREVIEW=1 python
ENV PATH "/root/.poetry/bin:/opt/venv/bin:${PATH}"

# Only copying these files here in order to take advantage of Docker cache. We only want the
# next stage (poetry install) to run if these files change, but not the rest of the app.
COPY pyproject.toml poetry.lock ./

# Currently poetry install is significantly slower than pip install, so we're creating a
# requirements.txt output and running pip install with it.
# Follow this issue: https://github.com/python-poetry/poetry/issues/338
# Setting --without-hashes because of this issue: https://github.com/pypa/pip/issues/4995
RUN poetry config virtualenvs.create false \
                && poetry export --without-hashes -f requirements.txt --dev \
                |  poetry run pip install -r /dev/stdin \
                && poetry debug

COPY  . ./

# Because initially we only copy the lock and pyproject file, we can only install the dependencies
# in the RUN above, as the `packages` portion of the pyproject.toml file is not
# available at this point. Now, after the whole package has been copied in, we run `poetry install`
# again to only install packages, scripts, etc. (and thus it should be very quick).
# See this issue for more context: https://github.com/python-poetry/poetry/issues/1899
RUN poetry install --no-dev --no-interaction

# We're setting the entrypoint to `poetry run` because poetry installed entry points aren't
# available in the PATH by default, but it is available for `poetry run`
ENTRYPOINT ["python", "ns0/app.py", "-f", "-n", "Foo", "test"]
