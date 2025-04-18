from pydantic import BaseModel
from datetime import date

class RegisterStep1Request(BaseModel):
    name: str
    name_kana: str
    gender: str
    birth_date: date
    postal_code: str
    address1: str
    address2: str
