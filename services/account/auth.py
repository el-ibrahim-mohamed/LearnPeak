from firebase_admin.db import Reference
import re
import bcrypt
import random
import uuid
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage


class Login:
    def __init__(self, db_root_ref: Reference):
        self.root_ref = db_root_ref

    def username_matches(self, username: str) -> bool:
        user_uid = self.root_ref.child(f"username_index/{username}").get()
        return user_uid if user_uid else False

    def email_matches(self, email: str) -> bool:
        user_uid = self.root_ref.child(
            f"email_index/{self.normalize_email(email)}"
        ).get()
        return user_uid if user_uid else False

    def password_matches(self, user_uid: str, password: str) -> bool:
        stored_hashed_password: str = self.root_ref.child(
            f"users/{user_uid}/auth/password_hash"
        ).get()

        if not stored_hashed_password:
            return False

        return bcrypt.checkpw(password.encode(), stored_hashed_password.encode())

    def get_user_info(self, user_uid: str):
        return {**self.root_ref.child(f"users/{user_uid}/info").get(), "uid": user_uid}
    
    def login(self, id: str, password: str) -> bool | dict:
        id_type = "username"
        if "@" in id:
            id_type = "email"

        if id_type == "username":
            user_uid = self.username_matches(id)
            if not user_uid:
                return False
        else:
            user_uid = self.email_matches(id)
            if not user_uid:
                return False

        if not self.password_matches(user_uid, password):
            return False

        return (
            user_uid,
            self.get_user_info(),
        )

    @staticmethod
    def normalize_email(email: str):
        email = email.strip().lower()
        for char in [".", "$", "#", "[", "]", "/"]:
            email = email.replace(char, ",")
        return email


class Signup:

    def __init__(
        self, db_root_ref: Reference, sender_email: str, sender_app_password: str
    ):
        self.root_ref = db_root_ref
        self.sender_email = sender_email
        self.sender_app_password = sender_app_password

    def validate_email(self, email: str) -> bool | str:
        if not email:
            return "Email required"

        email = email.strip().lower()

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(pattern, email):
            return "Invalid email"

        if self.root_ref.child(f"email_index/{self.normalize_email(email)}").get():
            return "Email already registered"

        return True

    def generate_otp(self, email: str, expiry_seconds: int = 3600) -> str:
        code = f"{random.randint(0, 999999):06d}"
        expiry_time = datetime.now() + timedelta(seconds=expiry_seconds)

        email = email.strip().lower()
        self.root_ref.child("email_verifications").child(
            self.normalize_email(email)
        ).set({"code": code, "expires": expiry_time.isoformat()})

        return code

    def send_otp(self, email: str) -> str:
        """Send account verification OTP email (styled HTML + plain fallback)."""

        otp = self.generate_otp(email)
        email = email.strip().lower()

        msg = EmailMessage()
        msg["Subject"] = "Verify your email • LearnPeak"
        msg["From"] = self.sender_email
        msg["To"] = email

        # Plain text fallback
        msg.set_content(
            f"Welcome to LearnPeak!\n\n"
            f"Your verification code is: {otp}\n\n"
            "This code expires in 1 hour.\n\n"
            "If you didn’t create an account, you can ignore this email.\n\n"
            "© LearnPeak"
        )

        # HTML version
        html_content = f"""
        <html>
        <body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial, sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="padding:20px;">
            <tr>
                <td align="center">
                
                <table width="400" cellpadding="0" cellspacing="0" style="background:#ffffff; padding:30px; border-radius:10px;">
                    
                    <tr>
                    <td align="center" style="font-size:22px; font-weight:bold; color:#333;">
                        LearnPeak
                    </td>
                    </tr>

                    <tr><td height="20"></td></tr>

                    <tr>
                    <td style="font-size:18px; color:#333; font-weight:bold;">
                        Welcome 👋
                    </td>
                    </tr>

                    <tr><td height="10"></td></tr>

                    <tr>
                    <td style="font-size:15px; color:#555;">
                        Thanks for joining LearnPeak! To complete your signup, use the verification code below:
                    </td>
                    </tr>

                    <tr><td height="25"></td></tr>

                    <tr>
                    <td align="center">
                        <div style="font-size:28px; letter-spacing:6px; font-weight:bold; color:#2d89ef;">
                        {otp}
                        </div>
                    </td>
                    </tr>

                    <tr><td height="25"></td></tr>

                    <tr>
                    <td style="font-size:14px; color:#777;">
                        This code will expire in <b>1 hour</b>.
                    </td>
                    </tr>

                    <tr><td height="20"></td></tr>

                    <tr>
                    <td style="font-size:13px; color:#999;">
                        If you didn’t create an account, you can safely ignore this email.
                    </td>
                    </tr>

                    <tr><td height="30"></td></tr>

                    <tr>
                    <td style="font-size:12px; color:#aaa;" align="center">
                        © LearnPeak
                    </td>
                    </tr>

                </table>

                </td>
            </tr>
            </table>
        </body>
        </html>
        """

        msg.add_alternative(html_content, subtype="html")

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.sender_email, self.sender_app_password)
                smtp.send_message(msg)
            return otp
        except Exception as e:
            print(f"Error sending email: {e}")
            return otp

    def validate_otp(self, email: str, code: str) -> bool | str:

        data = self.root_ref.child(
            f"email_verifications/{self.normalize_email(email)}"
        ).get()

        if not data:
            return "Verification code not found"

        if datetime.now() > datetime.fromisoformat(data["expires"]):
            return "Verification code expired"

        if code != data["code"]:
            return "Invalid verification code"

        # Remove verification after success
        self.root_ref.child(
            f"email_verifications/{self.normalize_email(email)}"
        ).delete()

        return True

    def validate_username(self, username: str) -> bool | str:
        if not username:
            return "Username required."

        if len(username) < 4:
            return "Username must be at least 4 characters long."

        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            return "Username can only contain letters, numbers, and underscores."

        if self.root_ref.child(f"username_index/{username}").get():
            return "Username is taken."

        return True

    def register_email_account(
        self,
        email: str,
        username: str,
        full_name: str,
        country: str,
        education: str,
        grade: str,
    ) -> bool:

        user_info = {
            "email": email.strip().lower(),
            "username": username,
            "full_name": full_name.strip().lower().title(),
            "country": country,
            "education": education,
            "grade": grade,
            "created_at": datetime.now().isoformat(),
        }

        user_auth = {
            "providers": {
                "google": False,
                "password": False,
            },
        }

        user_uid = str(uuid.uuid4())

        self.root_ref.update(
            {
                f"users/{user_uid}": {
                    "info": user_info,
                    "auth": user_auth,
                },
                f"username_index/{username}": user_uid,
                f"email_index/{self.normalize_email(email)}": user_uid,
            }
        )

        return user_uid

    @staticmethod
    def normalize_email(email: str):
        email = email.strip().lower()
        for char in [".", "$", "#", "[", "]", "/"]:
            email = email.replace(char, ",")
        return email

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()


class ForgotPassword:
    def __init__(
        self, db_root_ref: Reference, sender_email: str, sender_app_password: str
    ):
        self.root_ref = db_root_ref
        self.sender_email = sender_email
        self.sender_app_password = sender_app_password

    def find_user_by_id(self, id: str) -> str | None:
        """Find username by email or username. Returns username if found, None otherwise."""
        id = id.strip()

        # First check if it's a username
        if not "@" in id:
            username = id
            user_uid = self.root_ref.child(f"username_index/{username}").get()
            if user_uid:
                return (
                    user_uid,
                    username,
                    self.root_ref.child(f"users/{user_uid}/info/email").get(),
                )

        # Then check if it's an email
        email = id
        user_uid = self.root_ref.child(f"email_index/{email}").get()
        username = self.root_ref.child(f"users/{user_uid}/info/username").get()
        if user_uid:
            return (user_uid, username, email)

        return None, None

    def generate_reset_otp(self, user_uid: str, expiry_seconds: int = 3600) -> str:
        """Generate a 6-digit OTP and store it in the database."""
        otp = f"{random.randint(0, 999999):06d}"
        expiry_time = datetime.now() + timedelta(seconds=expiry_seconds)

        self.root_ref.child("password_resets").child(user_uid).set(
            {"otp": otp, "expires": expiry_time.isoformat(), "used": False}
        )

        return otp

    def send_reset_otp(self, user_uid: str, username: str, email: str) -> bool:
        """Send password reset OTP email."""
        otp = self.generate_reset_otp(user_uid)
        email = email.strip().lower()

        msg = EmailMessage()
        msg["Subject"] = "LearnPeak Password Reset Code"
        msg["From"] = self.sender_email
        msg["To"] = email

        msg.set_content(f"""
Hello {username},

We received a request to reset your password. Your reset code is:

{otp}

This code will expire in 1 hour. Enter this code in the app to reset your password.

If you didn't request this, you can ignore this email.

Best regards,
© LearnPeak
""")

        # HTML version
        html_content = f"""
        <html>
        <body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial, sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="padding:20px;">
            <tr>
                <td align="center">
                
                <table width="400" cellpadding="0" cellspacing="0" style="background:#ffffff; padding:30px; border-radius:10px;">
                    
                    <tr>
                    <td align="center" style="font-size:22px; font-weight:bold; color:#333;">
                        LearnPeak
                    </td>
                    </tr>

                    <tr><td height="20"></td></tr>

                    <tr>
                    <td style="font-size:16px; color:#555;">
                        Hello <b>{username}</b>,
                    </td>
                    </tr>

                    <tr><td height="15"></td></tr>

                    <tr>
                    <td style="font-size:15px; color:#555;">
                        We received a request to reset your password. Use the code below:
                    </td>
                    </tr>

                    <tr><td height="20"></td></tr>

                    <tr>
                    <td align="center">
                        <div style="font-size:28px; letter-spacing:6px; font-weight:bold; color:#2d89ef;">
                        {otp}
                        </div>
                    </td>
                    </tr>

                    <tr><td height="20"></td></tr>

                    <tr>
                    <td style="font-size:14px; color:#777;">
                        This code will expire in <b>1 hour</b>.
                    </td>
                    </tr>

                    <tr><td height="20"></td></tr>

                    <tr>
                    <td style="font-size:13px; color:#999;">
                        If you didn’t request this, you can safely ignore this email.
                    </td>
                    </tr>

                    <tr><td height="30"></td></tr>

                    <tr>
                    <td style="font-size:12px; color:#aaa;" align="center">
                        © LearnPeak
                    </td>
                    </tr>

                </table>

                </td>
            </tr>
            </table>
        </body>
        </html>
        """

        msg.add_alternative(html_content, subtype="html")

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.sender_email, self.sender_app_password)
                smtp.send_message(msg)
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def validate_reset_otp(self, user_uid: str, otp: str) -> bool | str:
        """Validate reset OTP. Returns True if valid, error message otherwise."""
        data = self.root_ref.child(f"password_resets/{user_uid}").get()

        if not data:
            return "Invalid OTP"

        if data.get("used"):
            return "OTP already used"

        if datetime.now() > datetime.fromisoformat(data["expires"]):
            return "OTP expired"

        if otp != data["otp"]:
            return "Invalid OTP"

        return

    def validate_password(self, password: str) -> bool | str:
        """Validate password strength."""
        if not password:
            return "Password required"

        if len(password) < 6:
            return "Password must be at least 6 characters"

        return True

    def reset_password_with_otp(
        self, user_uid: str, otp: str, new_password: str
    ) -> bool:
        """Reset password after validating OTP."""
        validation = self.validate_reset_otp(user_uid, otp)

        if validation is not True:
            return False

        hashed_password = self.hash_password(new_password)
        self.root_ref.child(f"users/{user_uid}/auth/password_hash").set(hashed_password)
        self.root_ref.child(f"password_resets/{user_uid}/used").set(True)

        return True

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
