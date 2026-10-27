"""Alembic environment: migrations run on the connection given by db.migrate."""

from alembic import context

from homestead_server.orm import Base

connection = context.config.attributes["connection"]
context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    render_as_batch=True,
)
with context.begin_transaction():
    context.run_migrations()
