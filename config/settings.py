from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    secret_key: str = "supersecretkey"
    mongo_uri: str = "mongodb+srv://<user>:<password>@cluster.mongodb.net/rcm_engine"
    gemini_api_key: str = ""
    pinecone_api_key: str = ""
    environment: str = "development"
    debug: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False
