"""initial schema

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('products',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('cost_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime()),
        sa.Index('ix_products_id', 'id'),
        sa.Index('ix_products_name', 'name'),
        sa.Index('ix_products_cost_price', 'cost_price'),
    )


def downgrade() -> None:
    op.drop_index('ix_products_cost_price', table_name='products')
    op.drop_index('ix_products_name', table_name='products')
    op.drop_index('ix_products_id', table_name='products')
    op.drop_table('products')
