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
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_name, **kwargs):
        return {"type": "string"}
    
class Books(BaseModel):
    title:str = Field(...,description="book title")
    sub_title:str = Field(...,description="book subtitle")
    price:int = Field(...,description="price of the book")
    author:str = Field(...,description="Author of the book")
    created_at:Optional[ datetime] = Field(default_factory= lambda: datetime.now(timezone.utc))
    updated_at : Optional [datetime] = Field(default_factory= lambda: datetime.now(timezone.utc))
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId:str}
        
        
class DeleteResponse(BaseModel):
    success: bool
    message: str
        
        
class UpdateBooks(BaseModel):
    title:Optional[str] = Field(description="book title")
    sub_title:Optional[str] = Field(description="book subtitle")
    price:Optional[int] = Field(description="price of the book")
    author:Optional[str] = Field(description="Author of the book")
    created_at:Optional[datetime] = Field(default_factory= lambda: datetime.now(timezone.utc))
    updated_at : Optional [datetime] = Field(default_factory= lambda: datetime.now(timezone.utc))
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId:str}
    

class ResponseBooks(BaseModel):
    id:PyObjectId = Field(...,alias="_id")
    title:str 
    sub_title:str
    price:int
    author:str
    created_at:Optional[datetime] = None
    updated_at : Optional [datetime] = None
    
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId:str}