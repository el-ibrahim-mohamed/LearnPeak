from firebase_admin.db import Reference
import re
import bcrypt
import random
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage


class Login:
    def __init__(self, db_root_ref: Reference):
        self.root_ref = db_root_ref

    def username_matches(self, username: str) -> bool:
        return self.root_ref.child(f"users/{username}").get() is not None

    def email_matches(self, email: str) -> bool:
        users = self.root_ref.child("users").get()

        if users:
            for username in users:
                user_email = users[username]["info"]["email"]
                if email == user_email:
                    return True, username

        return False

    def password_matches(self, username: str, password: str) -> bool:
        stored_hashed_password: str = self.root_ref.child(
            f"users/{username}/info/password"
        ).get()

        if not stored_hashed_password:
            return False

        return bcrypt.checkpw(password.encode(), stored_hashed_password.encode())

    def login(self, id: str, password: str) -> bool | dict:
        id_type = "username"
        if "@" in id:
            id_type = "email"

        if id_type == "username":
            if not self.username_matches(id):
                return False
        else:
            email_match = self.email_matches(id)
            if not email_match:
                return False
            id = email_match[1]

        if not self.password_matches(id, password):
            return False

        return (id, self.root_ref.child(f"users/{id}/info").get())


class Signup:

    def __init__(
        self, db_root_ref: Reference, sender_email: str, sender_app_password: str
    ):
        self.root_ref = db_root_ref
        self.sender_email = sender_email
        self.sender_app_password = sender_app_password

    def validate_username(self, username: str) -> bool | str:

        if not username:
            return "Username required"

        if len(username) < 4:
            return "Username must be at least 4 characters"

        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            return "Username can only contain letters, numbers, and underscores"

        if self.root_ref.child(f"users/{username}").get():
            return "Username is taken"

        return True

    def validate_email(self, email: str) -> bool | str:

        if not email:
            return "Email required"

        email = email.strip().lower()

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(pattern, email):
            return "Invalid email"

        users = self.root_ref.child("users").get()

        if users:
            for username in users:
                saved_email = users[username]["info"].get("email")
                if saved_email == email:
                    return "Email already registered"

        return True

    def validate_password(self, password: str) -> bool | str:

        if not password:
            return "Password required"

        if len(password) < 6:
            return "Password must be at least 6 characters"

        return True

    def generate_verification_code(self, email: str, expiry_seconds: int = 3600) -> str:

        code = f"{random.randint(0, 999999):06d}"
        expiry_time = datetime.now() + timedelta(seconds=expiry_seconds)

        email = email.strip().lower()
        self.root_ref.child("email_verifications").child(
            self.sanitize_email(email)
        ).set({"code": code, "expires": expiry_time.isoformat()})

        return code

    def send_verification_code(self, email: str) -> str:

        code = self.generate_verification_code(email)
        email = email.strip().lower()

        msg = EmailMessage()
        msg["Subject"] = "Your Learn Peak verification code"
        msg["From"] = self.sender_email
        msg["To"] = email

        msg.set_content(
            f"""
Welcome to Learn Peak!

Your verification code is:

{code}

This code will expire in 1 hour.

If you didn't request this, you can ignore this email.
"""
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(self.sender_email, self.sender_app_password)
            smtp.send_message(msg)

        return code

    def validate_verification_code(self, email: str, code: str) -> bool | str:

        data = self.root_ref.child(
            f"email_verifications/{self.sanitize_email(email)}"
        ).get()

        if not data:
            return "Verification code not found"

        if datetime.now() > datetime.fromisoformat(data["expires"]):
            return "Verification code expired"

        if code != data["code"]:
            return "Invalid verification code"

        # Remove verification after success
        self.root_ref.child(
            f"email_verifications/{self.sanitize_email(email)}"
        ).delete()

        return True

    def hash_password(self, password: str) -> str:

        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)

        return hashed.decode()

    def signup_user(
        self,
        email: str,
        password: str,
        username: str,
        full_name: str,
        country: str,
        education: str,
        grade: str,
    ) -> bool:

        hashed_password = self.hash_password(password)

        user_info = {
            "email": email.strip().lower(),
            "password": hashed_password,
            "full_name": full_name.title(),
            "country": country,
            "education": education,
            "grade": grade,
            "created_at": datetime.now().isoformat(),
        }

        self.root_ref.child(f"users/{username}/info").set(user_info)

        return True

    @staticmethod
    def sanitize_email(email: str):
        for char in [".", "$", "#", "[", "]", "/"]:
            email = email.replace(char, "")
        return email
