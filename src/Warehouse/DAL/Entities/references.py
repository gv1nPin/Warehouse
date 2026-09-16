from sqlalchemy import ForeignKey, Identity, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Warehouse.DAL.Database import Base


class RolePermission(Base):
    __tablename__ = "RolePermissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("Roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("Permissions.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Role(Base):
    __tablename__ = "Roles"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    role_name: Mapped[str] = mapped_column(Text, unique=True)

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="RolePermissions", back_populates="roles"
    )
    employees: Mapped[list["Employee"]] = relationship(back_populates="role")


class Permission(Base):
    __tablename__ = "Permissions"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    permission_name: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    roles: Mapped[list["Role"]] = relationship(
        secondary="RolePermissions", back_populates="permissions"
    )


class Status(Base):
    __tablename__ = "Statuses"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    status_name: Mapped[str] = mapped_column(Text, unique=True)


class Measurement(Base):
    __tablename__ = "Measurements"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    measurement_name: Mapped[str] = mapped_column(Text, unique=True)

    products: Mapped[list["Product"]] = relationship(back_populates="measurement")
