from datetime import datetime
from importlib.util import find_spec
from typing import Literal, get_args, get_origin

if find_spec("pydantic") is not None:
    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import Field
    from pydantic import ValidationError

    class ContractModel(_PydanticBaseModel):
        pass
else:
    _MISSING = object()

    class FieldInfo:
        def __init__(self, default=_MISSING, *, default_factory=None, min_length: int | None = None):
            self.default = default
            self.default_factory = default_factory
            self.min_length = min_length

    def Field(default=_MISSING, *, default_factory=None, min_length: int | None = None) -> FieldInfo:
        return FieldInfo(default, default_factory=default_factory, min_length=min_length)

    class ValidationError(Exception):
        def __init__(self, errors: list[dict]):
            super().__init__("validation error")
            self._errors = errors

        def errors(self) -> list[dict]:
            return self._errors

    class ContractModel:
        @classmethod
        def _fields(cls) -> dict:
            fields = {}
            for base in reversed(cls.mro()):
                fields.update(getattr(base, "__annotations__", {}))
            return fields

        @classmethod
        def model_validate(cls, payload: dict):
            errors = []
            values = {}
            for name, annotation in cls._fields().items():
                default = getattr(cls, name, _MISSING)
                if name in payload:
                    value = payload[name]
                elif isinstance(default, FieldInfo) and default.default_factory:
                    value = default.default_factory()
                elif isinstance(default, FieldInfo) and default.default is not _MISSING:
                    value = default.default
                elif default is not _MISSING and not isinstance(default, FieldInfo):
                    value = default
                else:
                    errors.append({"loc": (name,), "msg": "Field required"})
                    continue
                min_length = default.min_length if isinstance(default, FieldInfo) else None
                if min_length is not None and hasattr(value, "__len__") and len(value) < min_length:
                    errors.append({"loc": (name,), "msg": f"Value should have at least {min_length} items"})
                if get_origin(annotation) is Literal and value not in get_args(annotation):
                    errors.append({"loc": (name,), "msg": "Input should be a valid literal"})
                values[name] = value
            if errors:
                raise ValidationError(errors)
            return cls(**values)

        def __init__(self, **kwargs):
            for name in self._fields():
                default = getattr(self.__class__, name, _MISSING)
                if name in kwargs:
                    value = kwargs[name]
                elif isinstance(default, FieldInfo) and default.default_factory:
                    value = default.default_factory()
                elif isinstance(default, FieldInfo) and default.default is not _MISSING:
                    value = default.default
                elif default is not _MISSING and not isinstance(default, FieldInfo):
                    value = default
                else:
                    value = None
                setattr(self, name, value)

        def model_dump(self) -> dict:
            dumped = {}
            for name in self._fields():
                value = getattr(self, name)
                if isinstance(value, ContractModel):
                    value = value.model_dump()
                elif isinstance(value, list):
                    value = [item.model_dump() if isinstance(item, ContractModel) else item for item in value]
                elif isinstance(value, datetime):
                    value = value.isoformat()
                dumped[name] = value
            return dumped
