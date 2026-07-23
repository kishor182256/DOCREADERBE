from app.database.base import Base
from app.database.session import engine
from app.models.document import Document


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
