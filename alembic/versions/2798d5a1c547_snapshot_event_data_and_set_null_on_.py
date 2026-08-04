"""snapshot event data and set null on event delete

Revision ID: 2798d5a1c547
Revises: 122e654129f5
Create Date: 2026-07-31 10:49:10.939610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2798d5a1c547'
down_revision: Union[str, Sequence[str], None] = '122e654129f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add the new columns as NULLABLE first so Postgres doesn't reject existing rows
    op.add_column('orders', sa.Column('event_name', sa.String(), nullable=True))
    op.add_column('orders', sa.Column('event_price', sa.Numeric(precision=10, scale=2), nullable=True))

    # 2. Backfill: copy each order's actual event name/price from the events table,
    # while every order still has a live, matching event to read from
    op.execute("""
        UPDATE orders
        SET event_name = events.name,
            event_price = events.price
        FROM events
        WHERE orders.event_id = events.id
    """)

    # 3. Now that every existing row has real data, lock the columns down
    op.alter_column('orders', 'event_name', nullable=False)
    op.alter_column('orders', 'event_price', nullable=False)

    # 4. Foreign key change — this part Alembic detected correctly on its own
    op.drop_constraint(op.f('orders_event_id_fkey'), 'orders', type_='foreignkey')
    op.create_foreign_key(None, 'orders', 'events', ['event_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.create_foreign_key(op.f('orders_event_id_fkey'), 'orders', 'events', ['event_id'], ['id'])
    op.drop_column('orders', 'event_price')
    op.drop_column('orders', 'event_name')