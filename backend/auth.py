"""JWT email/password auth + role-based user management for the Retrofit platform."""
import os
import re
import uuid
import jwt
import bcrypt
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
JWT_ALG = "HS256"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Initial admin/owner accounts (seeded once; passwords stored only as bcrypt hashes).
SEED_ADMINS = [
    {"name": "Dean Foster", "email": "it@cphretrofit.co.uk", "password": ";hyaB1cZdA1RZk%6"},
    {"name": "Sean Crozier", "email": "sean@cphretrofit.co.uk", "password": ">+MZ>W@0XT>Pjv(0"},
    {"name": "Alex Leighton", "email": "alex@cphretrofit.co.uk", "password": "emsPv@1ZCsT0@w^J"},
    {"name": "Mark Crozier", "email": "mark@cphretrofit.co.uk", "password": "BXpHg0GuYzx&yD*8"},
    {"name": "Carolyn Crozier", "email": "accounts@cphretrofit.co.uk", "password": "#ky3dgt$?ZgV<WU%"},
]


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(uid: str, email: str) -> str:
    return jwt.encode({"sub": uid, "email": email, "type": "access",
                       "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, _secret(), algorithm=JWT_ALG)


def create_refresh_token(uid: str) -> str:
    return jwt.encode({"sub": uid, "type": "refresh",
                       "exp": datetime.now(timezone.utc) + timedelta(days=7)}, _secret(), algorithm=JWT_ALG)


def _set_cookies(resp: Response, uid: str, email: str):
    resp.set_cookie("access_token", create_access_token(uid, email), httponly=True, secure=True,
                    samesite="none", max_age=8 * 3600, path="/")
    resp.set_cookie("refresh_token", create_refresh_token(uid), httponly=True, secure=True,
                    samesite="none", max_age=7 * 86400, path="/")


def sanitize(u: dict) -> dict:
    return {"id": u.get("id") or str(u.get("_id")), "name": u.get("name"), "email": u.get("email"),
            "role": u.get("role", "user"), "is_active": u.get("is_active", True),
            "created_at": u.get("created_at")}


class LoginIn(BaseModel):
    email: str
    password: str


class ChangePwIn(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "user"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPwIn(BaseModel):
    new_password: str


def build_auth(db):
    auth_router = APIRouter(prefix="/api/auth")
    admin_router = APIRouter(prefix="/api/admin")

    async def _decode(request: Request) -> dict:
        token = request.cookies.get("access_token")
        if not token:
            h = request.headers.get("Authorization", "")
            if h.startswith("Bearer "):
                token = h[7:]
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = jwt.decode(token, _secret(), algorithms=[JWT_ALG])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Session expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid session")
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": payload["sub"]})
        if not user or not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="Account not available")
        return user

    async def require_user(request: Request) -> dict:
        return await _decode(request)

    async def require_admin(request: Request) -> dict:
        u = await _decode(request)
        if u.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return u

    async def _active_admin_count() -> int:
        return await db.users.count_documents({"role": "admin", "is_active": True})

    def _validate_new(email: str, password: str):
        if not EMAIL_RE.match((email or "").strip().lower()):
            raise HTTPException(status_code=422, detail="A valid email address is required")
        if not password or len(password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    # ---------------- Auth ----------------
    @auth_router.post("/login")
    async def login(body: LoginIn, response: Response):
        email = (body.email or "").strip().lower()
        key = f"lock:{email}"
        rec = await db.login_attempts.find_one({"_id": key})
        now = datetime.now(timezone.utc)
        if rec and rec.get("count", 0) >= 5 and rec.get("until") and rec["until"] > now.timestamp():
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
        user = await db.users.find_one({"email": email})
        if not user or not verify_password(body.password, user.get("password_hash", "")):
            cnt = (rec.get("count", 0) if rec else 0) + 1
            await db.login_attempts.update_one({"_id": key},
                {"$set": {"count": cnt, "until": (now + timedelta(minutes=15)).timestamp()}}, upsert=True)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="This account has been deactivated")
        await db.login_attempts.delete_one({"_id": key})
        _set_cookies(response, user["_id"], user["email"])
        return sanitize(user)

    @auth_router.post("/logout")
    async def logout(response: Response):
        response.delete_cookie("access_token", path="/", samesite="none", secure=True)
        response.delete_cookie("refresh_token", path="/", samesite="none", secure=True)
        return {"ok": True}

    @auth_router.get("/me")
    async def me(user: dict = Depends(require_user)):
        return sanitize(user)

    @auth_router.post("/refresh")
    async def refresh(request: Request, response: Response):
        token = request.cookies.get("refresh_token")
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = jwt.decode(token, _secret(), algorithms=[JWT_ALG])
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid session")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": payload["sub"]})
        if not user or not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="Account not available")
        response.set_cookie("access_token", create_access_token(user["_id"], user["email"]),
                            httponly=True, secure=True, samesite="none", max_age=8 * 3600, path="/")
        return sanitize(user)

    @auth_router.post("/change-password")
    async def change_password(body: ChangePwIn, user: dict = Depends(require_user)):
        if not verify_password(body.current_password, user.get("password_hash", "")):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if len(body.new_password or "") < 8:
            raise HTTPException(status_code=422, detail="New password must be at least 8 characters")
        await db.users.update_one({"_id": user["_id"]},
            {"$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True}

    # ---------------- Admin user management ----------------
    @admin_router.get("/users")
    async def list_users(_: dict = Depends(require_admin)):
        users = await db.users.find({}).sort("created_at", 1).to_list(500)
        return [sanitize(u) for u in users]

    @admin_router.post("/users")
    async def create_user(body: UserCreate, _: dict = Depends(require_admin)):
        email = (body.email or "").strip().lower()
        _validate_new(email, body.password)
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=422, detail="Role must be admin or user")
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=409, detail="A user with that email already exists")
        uid = str(uuid.uuid4())
        doc = {"_id": uid, "id": uid, "name": (body.name or "").strip() or email, "email": email,
               "password_hash": hash_password(body.password), "role": body.role, "is_active": True,
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.users.insert_one(doc)
        return sanitize(doc)

    @admin_router.put("/users/{uid}")
    async def update_user(uid: str, body: UserUpdate, admin: dict = Depends(require_admin)):
        user = await db.users.find_one({"_id": uid})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        updates = {}
        if body.name is not None:
            updates["name"] = body.name.strip()
        if body.email is not None:
            em = body.email.strip().lower()
            if not EMAIL_RE.match(em):
                raise HTTPException(status_code=422, detail="A valid email address is required")
            other = await db.users.find_one({"email": em})
            if other and other["_id"] != uid:
                raise HTTPException(status_code=409, detail="A user with that email already exists")
            updates["email"] = em
        # role / status changes with last-admin protection
        demoting = body.role is not None and body.role != user.get("role")
        deactivating = body.is_active is False and user.get("is_active", True)
        if (demoting and user.get("role") == "admin" and body.role != "admin") or (deactivating and user.get("role") == "admin"):
            if await _active_admin_count() <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last remaining admin")
        if body.role is not None:
            if body.role not in ("admin", "user"):
                raise HTTPException(status_code=422, detail="Role must be admin or user")
            if uid == admin["_id"] and body.role != "admin":
                raise HTTPException(status_code=400, detail="You cannot change your own role")
            updates["role"] = body.role
        if body.is_active is not None:
            if uid == admin["_id"] and body.is_active is False:
                raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
            updates["is_active"] = body.is_active
        if updates:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.users.update_one({"_id": uid}, {"$set": updates})
        return sanitize(await db.users.find_one({"_id": uid}))

    @admin_router.post("/users/{uid}/reset-password")
    async def reset_password(uid: str, body: ResetPwIn, _: dict = Depends(require_admin)):
        if len(body.new_password or "") < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
        user = await db.users.find_one({"_id": uid})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await db.users.update_one({"_id": uid},
            {"$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True}

    @admin_router.delete("/users/{uid}")
    async def delete_user(uid: str, admin: dict = Depends(require_admin)):
        user = await db.users.find_one({"_id": uid})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.get("role") == "admin" and user.get("is_active", True) and await _active_admin_count() <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last remaining admin")
        await db.users.delete_one({"_id": uid})
        return {"ok": True}

    async def ensure_auth_indexes():
        try:
            await db.users.create_index("email", unique=True)
            await db.login_attempts.create_index("_id")
        except Exception as e:
            logger.warning("auth index setup: %s", e)

    async def seed_admins():
        await ensure_auth_indexes()
        for a in SEED_ADMINS:
            email = a["email"].strip().lower()
            existing = await db.users.find_one({"email": email})
            if existing is None:
                uid = str(uuid.uuid4())
                await db.users.insert_one({
                    "_id": uid, "id": uid, "name": a["name"], "email": email,
                    "password_hash": hash_password(a["password"]), "role": "admin", "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat()})
            else:
                # keep owner accounts as active admins; never overwrite a changed password
                await db.users.update_one({"_id": existing["_id"]}, {"$set": {"role": "admin", "is_active": True}})

    return auth_router, admin_router, require_user, require_admin, seed_admins
