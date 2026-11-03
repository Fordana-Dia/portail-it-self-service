from fastapi import FastAPI
from app.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Portail IT Self-service")

@app.get("/")
def home():
    return {"message":"Portail IT opérationnel"} 
