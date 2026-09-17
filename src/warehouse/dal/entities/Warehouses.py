from typing import List, Optional
from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from warehouse.dal.entities.base.declarative import Base

class RolePermission(Base):
    __tablename__ = "RolePermissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("Permissions.id", ondelete="CASCADE"), primary_key=True)

class Role(Base):
    __tablename__ = "Roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    role_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    permissions: Mapped[List["Permission"]] = relationship(secondary="RolePermissions", back_populates="roles")

class Permission(Base):
    __tablename__ = "Permissions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    permission_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    roles: Mapped[List["Role"]] = relationship(secondary="RolePermissions", back_populates="permissions")

class Warehouse(Base):
    __tablename__ = "Warehouses"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Employee(Base):
    __tablename__ = "Employees"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    
    # Добавлены технические поля авторизации согласно вашему DDL
    login: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    
    warehouse: Mapped["Warehouse"] = relationship()
    role: Mapped["Role"] = relationship()
