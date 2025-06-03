from fastapi import APIRouter,HTTPException
import os
from dotenv import load_dotenv
from models.books import Books,ResponseBooks,PyObjectId,UpdateBooks,DeleteResponse
from config import get_book_collection
from typing import List
from bson import ObjectId,errors

load_dotenv()
book_root = APIRouter()
@book_root.post("/api/books",response_model = ResponseBooks)
async def insert_books(book:Books):
    collection = get_book_collection()
    
    existing_books = await collection.find_one({"title":book.title,"author":book.author})
    if existing_books:
        raise HTTPException(status_code=409, detail="Book already exists")
    
    book_data = book.model_dump(by_alias=True,exclude_none=True)
    
    inserted_book = await collection.insert_one(book_data)
    created_book = await collection.find_one({"_id":inserted_book.inserted_id})
    
    if created_book:
        created_book["_id"] = str(created_book["_id"])
        return ResponseBooks(**created_book)
    raise HTTPException(status_code=500, default="Created book failed")

@book_root.get("/api/books",response_model=List[ResponseBooks])
async def get_all_books():
    collection = get_book_collection()
    
    books = []
    async for book in collection.find():
        book["_id"] = str(book["_id"])
        books.append(ResponseBooks(**book))
    return books



# get book by id
@book_root.get("/api/books/{book_id}")
async def get_book_by_id(book_id:PyObjectId):
    collection = get_book_collection()
    
    book = await collection.find_one({"_id":ObjectId(book_id)})
    
    if book:
        book["_id"] = str(book["_id"])
        return ResponseBooks(**book)
    raise HTTPException(status_code=409,detail="Book not found")




# update book by id

@book_root.put("/api/books/{book_id}",response_model=ResponseBooks)
async def update_books(book_id:PyObjectId,book:UpdateBooks):
    collection = get_book_collection()
    
    book_data = book.model_dump(by_alias=True,exclude_unset=True)
    
    updated_book = await collection.update_one(
        {"_id":ObjectId(book_id)},
        {"$set":book_data}
    )
    
    if updated_book.modified_count == 1:
        result = await collection.find_one({"_id":ObjectId(book_id)})
        result["_id"] = str(result["_id"])
        return ResponseBooks(**result)
    
    existing_book = await collection.find_one({"_id":ObjectId(book_id)})
    if not existing_book:
        raise HTTPException(status_code=409,detail="Book not found")
    
    existing_book["_id"] = str(existing_book["_id"])
    return ResponseBooks(**existing_book)






@book_root.delete("/api/books/{book_id}",response_model = DeleteResponse)
async def deletes_book_by_id(book_id:PyObjectId):
    collection = get_book_collection()
    
    existing_book = await collection.delete_one({"_id":ObjectId(book_id)})
    if existing_book.deleted_count == 0:
        raise HTTPException(status_code=409,detail="Book not found to be deleted")
  
    return DeleteResponse(success=True, message="book deleted successfully")