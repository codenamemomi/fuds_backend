from sqlalchemy.orm import Session

from api.v1.models.user import User
from api.v1.schema.user import UserCreate, UserRead
from api.v1.services.base import BaseService


class UserService(BaseService[User, UserCreate, UserRead]):
    def __init__(self, db: Session):
        super().__init__(User, db)
