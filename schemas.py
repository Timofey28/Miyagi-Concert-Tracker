from pydantic import BaseModel, model_serializer

class UserInfo(BaseModel):
    mailing_is_activated: bool
    last_message_id: int | None

    @model_serializer()
    def __str__(self):
        return f'{int(self.mailing_is_activated)} {self.last_message_id if self.last_message_id else -1}'