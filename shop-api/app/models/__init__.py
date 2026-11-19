# Importing every model here means "import app.models" registers all tables.
from app.models.order import Order

__all__ = ["Order"]
