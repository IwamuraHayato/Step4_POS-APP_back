from pydantic import BaseModel
from datetime import date

class UserBase(BaseModel):
    name: str
    name_kana: str
    gender: str  # 'M', 'F', or 'U'
    birth_date: date
    postal_code: str
    address1: str
    address2: str
