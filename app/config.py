
from pydantic_settings import BaseSettings ,SettingsConfigDict


class Settings(BaseSettings):
    database_hostname :str
    database_port:str
    database_password:str
    database_name:str
    database_username:str
    model_config = SettingsConfigDict(env_file=".env") 





settings = Settings()