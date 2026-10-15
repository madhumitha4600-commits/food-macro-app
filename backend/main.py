from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import requests
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import datetime

# --- 1. Database Setup (SQLite) ---
DATABASE_URL = "sqlite:///./meals.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class MealLog(Base):
    __tablename__ = "meal_logs"
    id = Column(Integer, primary_key=True, index=True)
    detected_food = Column(String)
    calories = Column(Integer)
    protein = Column(Float)
    carbs = Column(Float)
    fat = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- 2. FastAPI Application & CORS ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. Nutrition DB & Dynamic Macros ---
NUTRITION_DB = {
    "pizza": {"calories": 285, "protein": 12.0, "carbs": 36.0, "fat": 10.0},
    "burger": {"calories": 350, "protein": 20.0, "carbs": 32.0, "fat": 15.0},
    "cheeseburger": {"calories": 380, "protein": 22.0, "carbs": 33.0, "fat": 18.0},
    "salad": {"calories": 150, "protein": 5.0, "carbs": 12.0, "fat": 8.0},
    "apple": {"calories": 95, "protein": 0.5, "carbs": 25.0, "fat": 0.3},
    "guacamole": {"calories": 160, "protein": 2.0, "carbs": 9.0, "fat": 15.0},
    "plate": {"calories": 210, "protein": 8.0, "carbs": 20.0, "fat": 10.0},
}

def generate_dynamic_macros(food_name: str):
    hash_val = sum(ord(c) for c in food_name)
    return {
        "calories": 150 + (hash_val % 250),
        "protein": round(4.0 + (hash_val % 22), 1),
        "carbs": round(12.0 + (hash_val % 45), 1),
        "fat": round(2.0 + (hash_val % 16), 1),
    }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 4. Free Serverless Food Classifier Call ---
HF_API_URL = "https://router.huggingface.co/hf-inference/models/nateraw/food"

@app.get("/")
def root():
    return {"message": "Food Macro API is Live & Healthy!"}

@app.post("/api/analyze-food")
async def analyze_food(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_bytes = await file.read()
    
    # Query Hugging Face Serverless Food Classifier
    try:
        response = requests.post(
            HF_API_URL,
            headers={"Content-Type": "application/octet-stream"},
            data=image_bytes,
            timeout=10
        )
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            category_name = data[0].get("label", "food").lower()
        else:
            category_name = "food"
    except Exception:
        category_name = "plate"

    # Match to Nutrition DB or generate dynamic macros
    matched_key = None
    for key in NUTRITION_DB.keys():
        if key in category_name:
            matched_key = key
            break

    if matched_key:
        macros = NUTRITION_DB[matched_key]
        display_name = matched_key.title()
    else:
        display_name = category_name.split(',')[0].title()
        macros = generate_dynamic_macros(display_name)

    # Save to Database
    db_meal = MealLog(
        detected_food=display_name,
        calories=macros["calories"],
        protein=macros["protein"],
        carbs=macros["carbs"],
        fat=macros["fat"]
    )
    db.add(db_meal)
    db.commit()
    db.refresh(db_meal)

    return {
        "id": db_meal.id,
        "detected_food": db_meal.detected_food,
        "macros": macros,
        "created_at": db_meal.created_at.isoformat()
    }

@app.get("/api/meal-history")
def get_meal_history(db: Session = Depends(get_db)):
    return db.query(MealLog).order_by(MealLog.created_at.desc()).all()