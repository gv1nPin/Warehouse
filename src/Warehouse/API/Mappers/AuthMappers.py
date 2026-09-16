from typing import Dict, Any
from Warehouse.API.Schemas.AuthDto import TokenOutputDTO

class AuthMapper:
    @staticmethod
    def to_token_output_dto(token_data: Dict[str, Any]) -> TokenOutputDTO:
        """Явно преобразует сырой словарь из BLL в строгий выходной DTO."""
        return TokenOutputDTO(
            access_token=token_data["access_token"],
            token_type=token_data["token_type"],
            expires_at=token_data["expires_at"]
        )
