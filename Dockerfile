# use an official Python runtime as a parent image
FROM python:3.11-slim

# set the working directory in the container
WORKDIR /app

# install Poetry, PostgreSQL development libraries, and PostgreSQL client utilities
RUN apt-get update \
    && apt-get install -y libpq-dev gcc postgresql-client \
    && pip install poetry

# copy the pyproject.toml and poetry.lock files
COPY pyproject.toml poetry.lock ./

# install dependencies via Poetry
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# copy the rest of the application code
COPY . /app/poems_data

# set the working directory to the poems_data folder
WORKDIR /app/poems_data

# run the application
CMD ["python", "data_dump.py"]