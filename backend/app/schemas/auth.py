from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")
    password: str = Field(min_length=8, max_length=18)
    recovery_question: str = Field(min_length=2, max_length=200)
    recovery_answer: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")
    password: str = Field(min_length=1, max_length=100)


class RecoveryQuestionRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")


class ResetPasswordRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")
    recovery_answer: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=18)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=8, max_length=18)
