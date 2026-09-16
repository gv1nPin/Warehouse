from Warehouse.DAL.Entities.Employees import Employee
from Warehouse.API.Schemas.Auth_dto import TokenOutputDTO

class AuthMapper:
    @staticmethod
    def to_token_dto(auth_result: dict) -> TokenOutputDTO:
        """Мапит сырой словарь токена из BLL в строгий TokenOutputDTO."""
        return TokenOutputDTO(
            access_token=auth_result["access_token"],
            token_type=auth_result["token_type"],
            expires_at=auth_result["expires_at"]
        )
