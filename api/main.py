from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi import WebSocket, WebSocketDisconnect
from audit import manager, broadcast_log, broadcast_alert
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from db import engine, get_db
from models import Base, User, Environment, AuditLog
from auth import hash_password, verify_password, create_token, get_current_user
from provisioner import provision_fullstack, destroy_environment, list_environments, get_container_stats
from datetime import datetime
from auth import hash_password, verify_password, create_token, get_current_user, check_brute_force, record_failed_attempt, get_remaining_attempts, login_attempts
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Portail IT Self-service")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPERS ROLES ---
def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return current_user

def require_developer(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "developer"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux développeurs")
    return current_user

def require_analyst(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "analyst"]:
        raise HTTPException(status_code=403, detail="Accès réservé aux analystes")
    return current_user

@app.get("/")
def home():
    return {"message": "Portail IT opérationnel"}

@app.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role, "team": current_user.team}

# --- AUTH ---
@app.post("/auth/register")
def register(username: str, password: str, role: str = "developer", team: str = "", db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Utilisateur déjà existant")
    user = User(username=username, role=role, team=team, password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Utilisateur créé", "id": user.id, "username": user.username}

@app.post("/auth/login")
@limiter.limit("5/minute")
def login(request: Request,form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Vérifier brute force
    check_brute_force(form_data.username)
    
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.password or not verify_password(form_data.password, user.password):
        # Vérifier si c'est la dernière tentative AVANT de l'enregistrer
        remaining_before = get_remaining_attempts(form_data.username)
        if remaining_before <= 1:
            asyncio.run(broadcast_alert("critical", "Compte bloqué", f"Le compte {form_data.username} a été bloqué après 5 tentatives échouées (possible brute force)", form_data.username))
        # Enregistrer tentative échouée (peut lever HTTPException si seuil atteint)
        record_failed_attempt(form_data.username)
        remaining = get_remaining_attempts(form_data.username)
        raise HTTPException(
            status_code=401,
            detail=f"Identifiants incorrects. Tentatives restantes : {remaining}"
        )
    
    # Réinitialiser les tentatives après succès
    login_attempts[form_data.username] = []
    
    # Log de connexion
    log = AuditLog(user_id=user.id, action="login", ressource="portail")
    db.add(log)
    db.commit()
    asyncio.run(broadcast_log(user.id, user.username, "login", "portail"))
    
    token = create_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}

# --- USERS (admin seulement) ---
@app.post("/users")
def create_user(username: str, password: str, role: str = "developer", team: str = "", db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Utilisateur déjà existant")
    user = User(username=username, role=role, team=team, password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.get("/users")
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return db.query(User).all()

# --- PROVISIONNEMENT (admin + developer) ---
@app.post("/provision/fullstack")
def provision(env_name: str, db: Session = Depends(get_db), current_user: User = Depends(require_developer)):
    try:
        # Vérifier le quota (max 3 pour developer, illimité pour admin)
        if current_user.role == "developer":
            active_envs = db.query(Environment).filter(
                Environment.requested_by == current_user.id,
                Environment.status == "running"
            ).count()
            if active_envs >= 3:
                asyncio.run(broadcast_alert("warning", "Quota dépassé", f"{current_user.username} a atteint son quota de 3 environnements", current_user.username))
                raise HTTPException(
                    status_code=429,
                    detail="Quota dépassé : vous avez atteint le maximum de 3 environnements actifs. Détruisez un environnement existant pour en créer un nouveau."
                )
        result = provision_fullstack(env_name)
        env = Environment(name=env_name, type="fullstack", requested_by=current_user.id, status="running")
        db.add(env)
        db.commit()
        log = AuditLog(user_id=current_user.id, action="provision_fullstack", ressource=env_name)
        db.add(log)
        db.commit()
        asyncio.run(broadcast_log(current_user.id, current_user.username, "provision_fullstack", env_name))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/provision/{env_name}")
def destroy(env_name: str, db: Session = Depends(get_db), current_user: User = Depends(require_developer)):
    try:
        result = destroy_environment(env_name)
        env = db.query(Environment).filter(Environment.name == env_name).first()
        if env:
            env.status = "destroyed"
            db.commit()
        log = AuditLog(user_id=current_user.id, action="destroy", ressource=env_name)
        db.add(log)
        db.commit()
        asyncio.run(broadcast_log(current_user.id, current_user.username, "destroy", env_name))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/provision/list")
def list_envs(current_user: User = Depends(get_current_user)):
    return list_environments()

# --- ENVIRONMENTS ---
@app.post("/environments/request")
def request_environment(name: str, type: str, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_developer)):
    env = Environment(name=name, type=type, requested_by=user_id)
    db.add(env)
    db.commit()
    log = AuditLog(user_id=user_id, action="create", ressource=name)
    db.add(log)
    db.commit()
    return {"status": "pending", "env": name}

@app.get("/environments")
def list_environments_db(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Environment).all()

# --- AUDIT (admin seulement) ---
@app.get("/audit")
def get_audit(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    
@app.get("/monitoring/stats")
def monitoring_stats(current_user: User = Depends(require_analyst)):
    return get_container_stats()

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
