# Books API 📚

A RESTful API built with FastAPI and MongoDB for managing a book collection. This API provides full CRUD (Create, Read, Update, Delete) operations for books with proper validation and error handling.

## 🚀 Features

- **Create Books**: Add new books with duplicate prevention
- **Read Books**: Retrieve all books or get specific book by ID
- **Update Books**: Modify existing book information
- **Delete Books**: Remove books from the collection
- **Data Validation**: Pydantic models for request/response validation
- **Error Handling**: Comprehensive error responses
- **Async Operations**: Non-blocking database operations
- **MongoDB Integration**: Efficient document storage and retrieval

## 🛠️ Tech Stack

- **Backend**: FastAPI
- **Database**: MongoDB
- **ODM**: Motor (Async MongoDB driver)
- **Validation**: Pydantic
- **Environment**: Python 3.8+

## 📦 Installation

### Prerequisites

- Python 3.8+
- MongoDB (v4.4 or higher)
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/emperorbj/fastapiDB.git
cd books-api
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install fastapi uvicorn motor python-dotenv pydantic
```

4. Create `.env` file:
```env
MONGODB_URI=mongodb://localhost:27017/books_db
DATABASE_NAME=books_db
COLLECTION_NAME=books
```

5. Start the server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 API Endpoints

### Base URL
```
http://localhost:8000
```

### Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/books` | Create a new book |
| GET | `/api/books` | Get all books |
| GET | `/api/books/{book_id}` | Get book by ID |
| PUT | `/api/books/{book_id}` | Update book by ID |
| DELETE | `/api/books/{book_id}` | Delete book by ID |

### 📝 Create Book
```http
POST /api/books
Content-Type: application/json

{
  "title": "The Great Gatsby",
  "author": "F. Scott Fitzgerald",
  "isbn": "978-0-7432-7356-5",
  "publication_year": 1925,
  "genre": "Fiction",
  "description": "A classic American novel"
}
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "title": "The Great Gatsby",
  "author": "F. Scott Fitzgerald",
  "isbn": "978-0-7432-7356-5",
  "publication_year": 1925,
  "genre": "Fiction",
  "description": "A classic American novel"
}
```

### 📖 Get All Books
```http
GET /api/books
```

**Response:**
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "title": "The Great Gatsby",
    "author": "F. Scott Fitzgerald",
    "isbn": "978-0-7432-7356-5",
    "publication_year": 1925,
    "genre": "Fiction",
    "description": "A classic American novel"
  }
]
```

### 🔍 Get Book by ID
```http
GET /api/books/507f1f77bcf86cd799439011
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "title": "The Great Gatsby",
  "author": "F. Scott Fitzgerald",
  "isbn": "978-0-7432-7356-5",
  "publication_year": 1925,
  "genre": "Fiction",
  "description": "A classic American novel"
}
```

### ✏️ Update Book
```http
PUT /api/books/507f1f77bcf86cd799439011
Content-Type: application/json

{
  "title": "The Great Gatsby - Updated",
  "description": "An updated description"
}
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "title": "The Great Gatsby - Updated",
  "author": "F. Scott Fitzgerald",
  "isbn": "978-0-7432-7356-5",
  "publication_year": 1925,
  "genre": "Fiction",
  "description": "An updated description"
}
```

### 🗑️ Delete Book
```http
DELETE /api/books/507f1f77bcf86cd799439011
```

**Response:**
```json
{
  "success": true,
  "message": "book deleted successfully"
}
```

## 🏗️ Project Structure

```
books-api/
├── main.py              # FastAPI application entry point
├── config.py            # Database configuration
├── models/
│   └── books.py         # Pydantic models
├── routes/
│   └── books.py         # API routes (your provided code)
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables
└── README.md           # This file
```

## 📊 Data Models

### Book Model (Input)
```python
{
  "title": str,           # Required
  "author": str,          # Required
  "isbn": str,            # Optional
  "publication_year": int, # Optional
  "genre": str,           # Optional
  "description": str      # Optional
}
```

### Response Model
```python
{
  "id": str,              # MongoDB ObjectId as string
  "title": str,
  "author": str,
  "isbn": str,
  "publication_year": int,
  "genre": str,
  "description": str
}
```

## ⚡ Error Handling

The API returns appropriate HTTP status codes:

- `200`: Success
- `201`: Created successfully
- `400`: Bad request (invalid data)
- `404`: Resource not found
- `409`: Conflict (duplicate book)
- `500`: Internal server error

### Error Response Format
```json
{
  "detail": "Error message description"
}
```

## 🔧 Configuration

### Environment Variables
```env
MONGODB_URI=mongodb://localhost:27017/books_db
DATABASE_NAME=books_db
COLLECTION_NAME=books
```

### Database Configuration (config.py)
```python
from motor.motor_asyncio import AsyncIOMotorClient
import os

client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
database = client[os.getenv("DATABASE_NAME")]

def get_book_collection():
    return database[os.getenv("COLLECTION_NAME")]
```

## 🧪 Testing

### Manual Testing with curl

1. **Create a book:**
```bash
curl -X POST "http://localhost:8000/api/books" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "1984",
    "author": "George Orwell",
    "publication_year": 1949,
    "genre": "Dystopian Fiction"
  }'
```

2. **Get all books:**
```bash
curl "http://localhost:8000/api/books"
```

3. **Get book by ID:**
```bash
curl "http://localhost:8000/api/books/507f1f77bcf86cd799439011"
```

### Testing with Python requests
```python
import requests

# Create a book
response = requests.post(
    "http://localhost:8000/api/books",
    json={
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "publication_year": 1960,
        "genre": "Fiction"
    }
)
print(response.json())
```

## 🐛 Known Issues

- Error message typo in insert_books function (`default` should be `detail`)
- HTTP status code inconsistency (409 used for not found, should be 404)
- Missing ObjectId validation for malformed IDs

## 🔄 Future Enhancements

- [ ] Add pagination for book listing
- [ ] Implement search functionality
- [ ] Add book categories/tags
- [ ] Include book cover image upload
- [ ] Add user authentication
- [ ] Implement book lending system
- [ ] Add book rating and review system
- [ ] Include data export functionality

## 📝 API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Opatola Bolaji** - - [YourGitHub](https://github.com/emperorbj)

## 📞 Support

For support, email support@booksapi.com or create an issue in the GitHub repository.

---

⭐ If you found this project helpful, please give it a star on GitHub!
