from fastapi import APIRouter, Depends, HTTPException, status
from dependency_injector.wiring import inject, Provide

from container import Container
from Warehouse.BLL.Services.AuthService.AuthService import AuthService, AuthException
from Warehouse.API.Schemas.Auth_dto import EmployeeRegisterInputDTO, LoginInputDTO, TokenOutputDTO

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
@inject
def register_employee(
    payload: EmployeeRegisterInputDTO,
    auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    try:
        employee_id = auth_service.register_employee(
            first_name=payload.first_name,
            last_name=payload.last_name,
            warehouse_id=payload.warehouse_id,
            role_id=payload.role_id,
            login=payload.login,
            plain_password=payload.password
        )
        return {"status": "success", "employee_id": employee_id}
    except AuthException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/login", response_model=TokenOutputDTO)
@inject
def login_employee(
    payload: LoginInputDTO,
    auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    try:
        token_data = auth_service.authenticate_employee(
            login=payload.login,
            plain_password=payload.password
        )
        return token_data
    except AuthException as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
