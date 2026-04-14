"""initial schema

"""
from alembic import op
import sqlalchemy as sa


revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('receipts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total', sa.Numeric(15, 2), nullable=False),
        sa.Column('items', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('email_sent', sa.String(length=10), server_default='pending'),
        sa.Index('ix_receipts_id', 'id'),
        sa.Index('ix_receipts_order_id', 'order_id'),
    )
    op.create_table('processed_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(255), unique=True, nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime()),
        sa.Index('ix_processed_events_id', 'id'),
    )


def downgrade() -> None:
    op.drop_index('ix_receipts_order_id', table_name='receipts')
    op.drop_index('ix_receipts_id', table_name='receipts')
    op.drop_table('processed_events')
    op.drop_table('receipts')
