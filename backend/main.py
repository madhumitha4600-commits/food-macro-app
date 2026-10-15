from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import torch
from torchvision import models, transforms
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

# --- 2. FastAPI Application & CORS Configuration ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite React default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. Expanded Nutrition Database & Dynamic Generator ---
NUTRITION_DB = {
    "pizza": {"calories": 285, "protein": 12.0, "carbs": 36.0, "fat": 10.0},
    "burger": {"calories": 350, "protein": 20.0, "carbs": 32.0, "fat": 15.0},
    "cheeseburger": {"calories": 380, "protein": 22.0, "carbs": 33.0, "fat": 18.0},
    "salad": {"calories": 150, "protein": 5.0, "carbs": 12.0, "fat": 8.0},
    "apple": {"calories": 95, "protein": 0.5, "carbs": 25.0, "fat": 0.3},
    "guacamole": {"calories": 160, "protein": 2.0, "carbs": 9.0, "fat": 15.0},
    "plate": {"calories": 210, "protein": 8.0, "carbs": 20.0, "fat": 10.0},
    "soup": {"calories": 130, "protein": 6.0, "carbs": 15.0, "fat": 4.0},
    "hotdog": {"calories": 290, "protein": 10.0, "carbs": 24.0, "fat": 16.0},
    "french fries": {"calories": 365, "protein": 4.0, "carbs": 48.0, "fat": 17.0},
    "bagel": {"calories": 250, "protein": 10.0, "carbs": 48.0, "fat": 1.5},
    "pretzel": {"calories": 380, "protein": 9.0, "carbs": 80.0, "fat": 3.0},
    "orange": {"calories": 62, "protein": 1.2, "carbs": 15.0, "fat": 0.2},
    "banana": {"calories": 105, "protein": 1.3, "carbs": 27.0, "fat": 0.3},
    "ice cream": {"calories": 207, "protein": 3.5, "carbs": 24.0, "fat": 11.0},
}

def generate_dynamic_macros(food_name: str):
    """Generates unique, deterministic macros for unmatched food items using hashing."""
    hash_val = sum(ord(c) for c in food_name)
    return {
        "calories": 150 + (hash_val % 250),
        "protein": round(4.0 + (hash_val % 22), 1),
        "carbs": round(12.0 + (hash_val % 45), 1),
        "fat": round(2.0 + (hash_val % 16), 1),
    }

# --- 4. ML Model Initialization ---
weights = models.ResNet18_Weights.DEFAULT
model = models.resnet18(weights=weights)
model.eval()
preprocess = weights.transforms()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 5. API Endpoints ---
@app.post("/api/analyze-food")
async def analyze_food(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    # Read and preprocess image
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    input_tensor = preprocess(image).unsqueeze(0)

    # Perform ML Inference
    with torch.no_grad():
        output = model(input_tensor)
        predicted_idx = torch.argmax(output, dim=1).item()

    # Get class name from ImageNet weights
    category_name = weights.meta["categories"][predicted_idx].lower()
    
    # Check for match in NUTRITION_DB
    matched_key = None
    for key in NUTRITION_DB.keys():
        if key in category_name:
            matched_key = key
            break

    # Assign macros from DB if found, otherwise compute unique dynamic macros
    if matched_key:
        macros = NUTRITION_DB[matched_key]
        display_name = matched_key.title()
    else:
        display_name = category_name.split(',')[0].title()
        macros = generate_dynamic_macros(display_name)

    # Save transaction to SQLite Database
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