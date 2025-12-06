import os
import re
import string
import secrets
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Use bcrypt for password hashing (production-safe)
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    from werkzeug.security import generate_password_hash, check_password_hash

# -------------------- Security Configuration from .env --------------------
TOKEN_EXPIRY_MINUTES = int(os.getenv("TOKEN_EXPIRY_MINUTES", "30"))
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "30"))
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))


def generate_secure_token(length=32):
    """Generate a cryptographically secure URL-safe token using secrets.token_urlsafe"""
    return secrets.token_urlsafe(length)


def hash_password(password: str) -> str:
    """Hash password using bcrypt (or werkzeug as fallback)"""
    if BCRYPT_AVAILABLE:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    else:
        return generate_password_hash(password, method='pbkdf2:sha256:600000')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash using bcrypt (or werkzeug as fallback)"""
    if BCRYPT_AVAILABLE:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            # Fallback for old werkzeug hashes during migration
            if password_hash.startswith('pbkdf2:'):
                from werkzeug.security import check_password_hash
                return check_password_hash(password_hash, password)
            return False
    else:
        return check_password_hash(password_hash, password)


def generate_user_id():
    """Generate a unique user ID"""
    return str(uuid.uuid4())


class UserManager:
    def __init__(self, users_collection, use_mongo=True):
        self.users_col = users_collection
        self.use_mongo = use_mongo
        # Use environment variables for security settings
        self.PASSWORD_MIN_LENGTH = PASSWORD_MIN_LENGTH
        self.PASSWORD_REGEX = rf"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{{{PASSWORD_MIN_LENGTH},}}$"
        self.MAX_LOGIN_ATTEMPTS = MAX_LOGIN_ATTEMPTS
        self.LOCKOUT_DURATION = timedelta(minutes=LOCKOUT_DURATION_MINUTES)

    def validate_email(self, email):
        """Validate email format"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_regex, email))

    def validate_password(self, password):
        """Validate password strength"""
        if not password:
            return False, "Password cannot be empty"
        if len(password) < self.PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {self.PASSWORD_MIN_LENGTH} characters"
        if not re.match(self.PASSWORD_REGEX, password):
            return False, "Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character"
        return True, ""

    def create_user(self, username, password, email, name, role="teacher"):
        """Create a new user with validated credentials"""
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters"
        if not self.validate_email(email):
            return False, "Invalid email format"
        if self.users_col.find_one({"username": username}):
            return False, "Username already exists"
        if self.users_col.find_one({"email": email}):
            return False, "Email already exists"

        is_valid, error = self.validate_password(password)
        if not is_valid:
            return False, error

        try:
            user_data = {
                "user_id": generate_user_id(),  # Unique user ID for referential integrity
                "username": username,
                "password": hash_password(password),  # bcrypt hash
                "email": email,
                "name": name,
                "role": role,
                "created_at": datetime.now(),
                "last_login": None,
                "failed_attempts": 0,
                "is_locked": False,
                "lockout_until": None,
                "status": "active",  # Auto-activate (no email verification)
                # Password reset fields (initialized as null)
                "reset_token": None,
                "token_expiry": None
            }
            self.users_col.insert_one(user_data)
            return True, "User created successfully in MongoDB."
        except Exception as e:
            return False, f"Error creating user: {str(e)}"

    def authenticate_user(self, username, password):
        """Authenticate user with rate limiting and lockout"""
        user = self.users_col.find_one({"username": username})
        if not user:
            return False, "User not found"

        if user.get("is_locked", False):
            lockout_until = user.get("lockout_until")
            if lockout_until and lockout_until > datetime.now():
                return False, f"Account locked until {lockout_until}"
            else:
                self.users_col.update_one(
                    {"username": username},
                    {"$set": {"is_locked": False, "failed_attempts": 0, "lockout_until": None}}
                )

        if user.get("status") != "active":
            return False, "Account is inactive"

        # If password is None, it's a session check (cookie-based)
        if password is None:
            return True, {
                "username": username,
                "role": user.get("role"),
                "name": user.get("name"),
                "email": user.get("email")
            }

        if verify_password(password, user.get("password", "")):
            self.users_col.update_one(
                {"username": username},
                {
                    "$set": {
                        "last_login": datetime.now(),
                        "failed_attempts": 0,
                        "lockout_until": None
                    }
                }
            )
            return True, {
                "username": username,
                "role": user.get("role"),
                "name": user.get("name"),
                "email": user.get("email")
            }
        else:
            failed_attempts = user.get("failed_attempts", 0) + 1
            is_locked = failed_attempts >= self.MAX_LOGIN_ATTEMPTS
            lockout_until = datetime.now() + self.LOCKOUT_DURATION if is_locked else None

            self.users_col.update_one(
                {"username": username},
                {
                    "$set": {
                        "failed_attempts": failed_attempts,
                        "is_locked": is_locked,
                        "lockout_until": lockout_until
                    }
                }
            )
            return False, "Invalid password" if not is_locked else f"Account locked until {lockout_until}"

    def change_password(self, username, current_password, new_password):
        """Change user password with validation"""
        auth_success, _ = self.authenticate_user(username, current_password)
        if not auth_success:
            return False, "Current password is incorrect"

        is_valid, error = self.validate_password(new_password)
        if not is_valid:
            return False, error

        try:
            self.users_col.update_one(
                {"username": username},
                {
                    "$set": {
                        "password": hash_password(new_password),  # bcrypt hash
                        "last_modified": datetime.now()
                    }
                }
            )
            return True, "Password updated successfully in MongoDB."
        except Exception as e:
            return False, f"Error updating password: {str(e)}"

    def find_user_by_email(self, email):
        """Find user by email address"""
        return self.users_col.find_one({"email": email})

    def generate_reset_token(self, email):
        """
        Generate a cryptographically secure password reset token
        Token expiry is configured via TOKEN_EXPIRY_MINUTES in .env
        """
        user = self.find_user_by_email(email)
        if not user:
            return False, None, "Email not found"

        try:
            # Generate cryptographically secure URL-safe token
            token = secrets.token_urlsafe(32)
            # Token expires based on TOKEN_EXPIRY_MINUTES from .env (default: 30 minutes)
            expires = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY_MINUTES)

            self.users_col.update_one(
                {"email": email},
                {
                    "$set": {
                        "reset_token": token,
                        "token_expiry": expires
                    }
                }
            )
            return True, token, user.get("name", user.get("username", "User"))
        except Exception as e:
            return False, None, f"Error generating reset token: {str(e)}"

    def validate_reset_token(self, token):
        """
        Validate a password reset token
        Returns: (is_valid, user_data or error_message)
        """
        if not token:
            return False, "No reset token provided"

        # Find user with this token
        user = self.users_col.find_one({"reset_token": token})

        if not user:
            return False, "Invalid reset token"

        # Check token expiry
        token_expiry = user.get("token_expiry")
        if not token_expiry:
            return False, "Reset token has expired"

        if token_expiry < datetime.utcnow():
            return False, "Reset token has expired"

        return True, {
            "username": user.get("username"),
            "email": user.get("email"),
            "name": user.get("name")
        }

    def reset_password(self, token, new_password):
        """
        Reset password using a valid token
        - Validates token
        - Hashes new password with bcrypt
        - Clears reset_token and token_expiry after use
        """
        # Validate password strength
        is_valid, error = self.validate_password(new_password)
        if not is_valid:
            return False, error

        # Validate token
        token_valid, result = self.validate_reset_token(token)
        if not token_valid:
            return False, result

        try:
            # Update password and clear reset token
            self.users_col.update_one(
                {"reset_token": token},
                {
                    "$set": {
                        "password": hash_password(new_password),  # bcrypt hash
                        "reset_token": None,  # Clear token after use
                        "token_expiry": None,  # Clear expiry after use
                        "last_modified": datetime.now(),
                        # Also unlock account if it was locked
                        "is_locked": False,
                        "failed_attempts": 0,
                        "lockout_until": None
                    }
                }
            )
            return True, "Password reset successfully! You can now login with your new password."
        except Exception as e:
            return False, f"Error resetting password: {str(e)}"

    def clear_expired_tokens(self):
        """Clear all expired reset tokens (maintenance function)"""
        try:
            self.users_col.update_many(
                {"token_expiry": {"$lt": datetime.utcnow()}},
                {"$set": {"reset_token": None, "token_expiry": None}}
            )
        except Exception:
            pass  # Non-critical maintenance operation
