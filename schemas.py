from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    id: int
    mailing_is_activated: bool
    last_message_id: int | None

    username: Optional[str]
    first_name: str
    last_name: Optional[str]

    def __str__(self):
        if self.username:
            return f'[{self.__get_name()}](https://t.me/{self.username}){f"  {self.last_message_id}" if self.last_message_id else ""}'
        else:
            return f'{self.__get_name()}{f"  {self.last_message_id}" if self.last_message_id else ""}'

    def __get_name(self):
        return f'{self.first_name} {self.last_name}' if self.last_name else self.first_name
