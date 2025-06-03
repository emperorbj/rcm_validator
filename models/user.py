from pydantic import BaseModel,Field
from typing import Optional
from datetime import datetime,timezone
from bson import ObjectId

class PyObjectId(str):
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
        
    @classmethod
    def validate(cls,v,*args,**kwargs):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid Objectid")
        return str(v)


class Users(BaseModel):
    first_name: str = Field(description="User's first name",min_length=1)
    last_name:str = Field(description="User's last name",min_length=1)
    email:str = Field(...,description="User's email")
    password:str = Field(...,description="User's password")
    created_at: datetime  = Field(default_factory= lambda : datetime.now(timezone.utcnow()))
    isVerified:Optional[None] = Field(description="User is verified",default=False)
    
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId:str}

class LoginUser(BaseModel):
    email:str = Field(...,description="Email of user")
    password:str = Field(...,description="Password of user")
    
    
class UserResponse(BaseModel):
    id:PyObjectId = Field(...,alias="_id")
    first_name:str
    last_name:str
    email:str
    isVerified:bool
    
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId:str}
        