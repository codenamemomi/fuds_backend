from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
ReadSchemaType = TypeVar("ReadSchemaType")


class BaseService(Generic[ModelType, CreateSchemaType, ReadSchemaType]):
    def __init__(self, model_class: type[ModelType], db: Session):
        self.model_class = model_class
        self.db = db

    def create(self, payload: CreateSchemaType, commit: bool = True) -> ModelType:
        model_data = payload.model_dump()
        model_instance = self.model_class(**model_data)
        self.db.add(model_instance)
        if commit:
            self.db.commit()
            self.db.refresh(model_instance)
        return model_instance

    def get_all(self) -> list[ModelType]:
        return self.db.query(self.model_class).all()

    def get_by_id(self, item_id: int) -> ModelType | None:
        return self.db.query(self.model_class).filter(self.model_class.id == item_id).first()
