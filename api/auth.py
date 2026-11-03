import os
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
from db import get_db
from models import User
import bcrypt
from collections import defaultdict

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Stockage des tentatives échouées
login_attempts = defaultdict(list)
blocked_users = {}

MAX_ATTEMPTS = 5
BLOCK_DURATION_MINUTES = 5

def check_brute_force(username: str):
    now = datetime.utcnow()
    
    # Vérifier si bloqué
    if username in blocked_users:
        unblock_time = blocked_users[username]
        if now < unblock_time:
            remaining = int((unblock_time - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Compte bloqué suite à trop de tentatives. Réessayez dans {remaining} minute(s)."
            )
        else:
            # Débloquer
            del blocked_users[username]
            login_attempts[username] = []

    # Nettoyer les tentatives de plus de 5 minutes
    login_attempts[username] = [
        t for t in login_attempts[username]
        if now - t < timedelta(minutes=BLOCK_DURATION_MINUTES)
    ]

def record_failed_attempt(username: str):
    now = datetime.utcnow()
    login_attempts[username].append(now)
    
    if len(login_attempts[username]) >= MAX_ATTEMPTS:
        blocked_users[username] = now + timedelta(minutes=BLOCK_DURATION_MINUTES)
        raise HTTPException(
            status_code=429,
            detail=f"Compte bloqué après {MAX_ATTEMPTS} tentatives échouées. Réessayez dans {BLOCK_DURATION_MINUTES} minutes."
        )

def get_remaining_attempts(username: str) -> int:
    now = datetime.utcnow()
    recent = [t for t in login_attempts[username] if now - t < timedelta(minutes=BLOCK_DURATION_MINUTES)]
    return MAX_ATTEMPTS - len(recent)

def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")
