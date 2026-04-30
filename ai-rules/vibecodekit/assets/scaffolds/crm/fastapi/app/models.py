from pydantic import BaseModel, EmailStr


class NewContact(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None


class Contact(NewContact):
    id: int
