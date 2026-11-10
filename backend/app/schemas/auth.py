from pydantic import BaseModel, Field, model_validator

from app.security.passwords import normalize_recovery_answer


class RegisterRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")
    password: str = Field(min_length=8, max_length=18)
    recovery_question: str = Field(min_length=2, max_length=200)
    recovery_answer: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def reject_blank_recovery(self) -> "RegisterRequest":
        if not self.recovery_question.strip():
            raise ValueError("找回问题不能为空")
        if not normalize_recovery_answer(self.recovery_answer):
            raise ValueError("找回答案不能为空")
        return self


class LoginRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")
    password: str = Field(min_length=1, max_length=100)


class RecoveryQuestionRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")


class ResetPasswordRequest(BaseModel):
    username: str = Field(pattern=r"^[0-9]{8,18}$")
    recovery_question: str = Field(min_length=2, max_length=200)
    recovery_answer: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=18)

    @model_validator(mode="after")
    def reject_blank_recovery(self) -> "ResetPasswordRequest":
        if not self.recovery_question.strip():
            raise ValueError("找回问题不能为空")
        if not normalize_recovery_answer(self.recovery_answer):
            raise ValueError("找回答案不能为空")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=8, max_length=18)
