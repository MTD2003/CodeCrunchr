from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CodeCrunchrBase(DeclarativeBase):
    pass


class TestModel(CodeCrunchrBase):
    __tablename__ = "codecrunchr_test"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str]


__all__ = ["CodeCrunchrBase", "TestModel"]
