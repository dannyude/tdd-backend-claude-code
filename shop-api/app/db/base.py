from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Every model inherits from this. Base.metadata knows all tables."""
