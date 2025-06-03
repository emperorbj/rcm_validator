from fastapi import APIRouter,HTTPException
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv
from models.user import Users,UserResponse,LoginUser
from config import get_collection
import bcrypt


load_dotenv()

signup_root = APIRouter()
# key = os.getenv("FERNET_KEY").encode()
# # key = Fernet.generate_key()
# print(key)

# cipher = Fernet(key)





@signup_root.post("/api/signup")
async def sign_up(user:Users,response_model = UserResponse ):
    
    collection = get_collection()
    
    # crypted_first_name = cipher.encrypt(user.first_name.encode()).decode()
    # crypted_last_name = cipher.encrypt(user.last_name.encode()).decode()
    crypted_password = bcrypt.hashpw(user.password.encode(),bcrypt.gensalt()).decode()
    
    data = {
       "first_name":user.first_name,
       "last_name":user.last_name,
       "email":user.email,
       "password":crypted_password,
       "isVerified":user.isVerified,
       "created_at":user.created_at
    }
    
    existing_user = await collection.find_one({"email":user.email})
    
    if existing_user:
        raise HTTPException(status_code=400,detail="User already exist")
    
    new_user = await collection.insert_one(data)
    inserted_user = await collection.find_one({"_id":new_user.inserted_id})
    
    return UserResponse(**inserted_user)




@signup_root.post("/api/login")
async def login(user:LoginUser, response_model = UserResponse):
    collection = get_collection()
    login_user = await collection.find_one({"email":user.email})
    
    if not login_user:
        raise HTTPException(status_code=401,detail="User cannot be found")
    
    stored_password = login_user["password"]
    if not bcrypt.checkpw(user.password.encode(),stored_password.encode()):
        raise HTTPException(status_code=401,detail="Password is invalid")
    
    response_data = {
        "_id": login_user["_id"],
        "first_name": login_user["first_name"],
        "last_name": login_user["last_name"],
        "email": login_user["email"],
        "created_at": login_user["created_at"],
        "isVerified": login_user["isVerified"]
    }
    
   
    
    
    return UserResponse(**response_data)