from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer
import os
import random
import aiofiles

app = FastAPI()

# Database URL - Use a cloud database like PostgreSQL for production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")
database = Database(DATABASE_URL)
metadata = MetaData()

# Define users table
users_table = Table(
    "users",
    metadata,
    Column("phone", String, primary_key=True),
    Column("name", String),
    Column("code", Integer)
)

# Define posts table
posts_table = Table(
    "posts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("first_name", String),
    Column("second_name", String),
    Column("third_name", String),
    Column("phone", String),
    Column("image_name", String)
)

# Create engine
engine = create_engine(DATABASE_URL, echo=True, future=True)

# Create tables
metadata.create_all(bind=engine)

# Ensure the uploads directory exists
uploads_dir = "uploads_img"
os.makedirs(uploads_dir, exist_ok=True)

class PhoneNumber(BaseModel):
    phone: str
    name: str

class VerificationCode(BaseModel):
    phone: str
    code: str

@app.on_event("startup")
async def startup():
    await database.connect()
    print("Database connected")

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
    print("Database disconnected")

@app.post("/send_code")
async def send_code(phone_number: PhoneNumber):
    code = random.randint(1000, 9999)

    query = users_table.select().where(users_table.c.phone == phone_number.phone)
    existing_user = await database.fetch_one(query)

    if existing_user:
        query = users_table.update().where(users_table.c.phone == phone_number.phone).values(code=code, name=phone_number.name)
    else:
        query = users_table.insert().values(phone=phone_number.phone, name=phone_number.name, code=code)

    await database.execute(query)
    return {"message": "كود التحقق تم إرساله"}

@app.post("/verify_code")
async def verify_code(verification: VerificationCode):
    query = users_table.select().where(users_table.c.phone == verification.phone)
    user = await database.fetch_one(query)
    
    if user is None:
        raise HTTPException(status_code=404, detail="رقم الهاتف غير موجود")
    
    stored_code = user['code']
    
    if int(verification.code) != stored_code:
        raise HTTPException(status_code=400, detail="كود غير صحيح")
    
    return {"message": "تم التحقق من الكود بنجاح"}

@app.post("/user_post")
async def user_post(
    first_name: str = Form(...),
    second_name: str = Form(...),
    third_name: str = Form(...),
    phone: str = Form(...),
    file: UploadFile = File(...),
):
    image_name = file.filename
    image_path = os.path.join(uploads_dir, image_name)

    async with aiofiles.open(image_path, "wb") as image_file:
        content = await file.read()
        await image_file.write(content)

    query = posts_table.insert().values(
        first_name=first_name,
        second_name=second_name,
        third_name=third_name,
        phone=phone,
        image_name=image_name
    )

    await database.execute(query)
    return {"message": "تم رفع المنشور بنجاح"}

@app.get("/posts")
async def get_all_posts():
    query = posts_table.select()
    posts = await database.fetch_all(query)
    
    if not posts:
        raise HTTPException(status_code=404, detail="لا توجد منشورات")
    
    result = [
        {
            "id": post["id"],
            "first_name": post["first_name"],
            "second_name": post["second_name"],
            "third_name": post["third_name"],
            "phone": post["phone"],
            "image_name": post["image_name"]
        } for post in posts
    ]
    
    return {"posts": result}

app.mount("/uploads_img", StaticFiles(directory=uploads_dir), name="uploads_img")
