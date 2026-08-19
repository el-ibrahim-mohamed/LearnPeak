from firebase_admin.db import Reference

from services.account.auth import AuthUtils, EmailService, OTPManager, Signup

# ---------------------------------------------------------
# ACCOUNT SETTINGS SERVICE
# ---------------------------------------------------------


class AccountSettingsService:
    def __init__(
        self,
        db_root_ref: Reference,
        sender_email: str,
        sender_app_password: str,
    ):
        self.root_ref = db_root_ref
        self.signup_service = Signup(db_root_ref, sender_email, sender_app_password)
        self.email_service = EmailService(sender_email, sender_app_password)
        self.otp_mgr = OTPManager(db_root_ref)

    def update_user_info(
        self, user_uid: str, field: str, value: str
    ) -> tuple[bool, str]:
        """Update a user profile field such as country, education, or grade."""
        allowed_fields = {"country", "education", "grade"}

        if field not in allowed_fields:
            return False, "Unsupported info field."

        clean_value = (value or "").strip()
        if not clean_value:
            return False, "This field cannot be empty."

        self.root_ref.child(f"users/{user_uid}/info/{field}").set(clean_value)
        return True, "Saved"

    def update_email(
        self, user_uid: str, email: str, current_email: str = ""
    ) -> tuple[bool, str]:
        """Update the user email and maintain the Firebase email index."""
        new_email = (email or "").strip().lower()
        current_email = (current_email or "").strip().lower()

        if not new_email:
            return False, "Email is required."

        if new_email == current_email:
            return True, "No changes made."

        validation = self.signup_service.validate_email(new_email)
        if validation is not True:
            return False, validation

        old_key = AuthUtils.normalize_email(current_email)
        new_key = AuthUtils.normalize_email(new_email)

        updates = {}
        if old_key:
            updates[f"email_index/{old_key}"] = None

        updates[f"users/{user_uid}/info/email"] = new_email
        updates[f"email_index/{new_key}"] = user_uid
        self.root_ref.update(updates)

        return True, "Email updated"

    def update_username(
        self, user_uid: str, username: str, current_username: str = ""
    ) -> tuple[bool, str]:
        """Update the user username and maintain the Firebase username index."""
        new_username = (username or "").strip()
        current_username = (current_username or "").strip()

        if not new_username:
            return False, "Username is required."

        if new_username == current_username:
            return True, "No changes made."

        validation = self.signup_service.validate_username(new_username)
        if validation is not True:
            return False, validation

        updates = {}

        if current_username:
            updates[f"username_index/{current_username}"] = None

        updates[f"users/{user_uid}/info/username"] = new_username
        updates[f"username_index/{new_username}"] = user_uid
        self.root_ref.update(updates)

        return True, "Username updated"

    def send_current_email_verification(
        self, user_uid: str, current_email: str
    ) -> tuple[bool, str]:
        """Send a 6-digit OTP to the current email to confirm identity."""
        current_email = (current_email or "").strip().lower()
        if not current_email:
            return False, "Current email is missing."

        otp_store_path = f"account_email_change/{user_uid}/current_email"
        otp = self.otp_mgr.generate_and_store_otp(otp_store_path)

        text_fallback = f"""
        Hello,

        We received a request to change your LearnPeak account email.

        Your verification code is: {otp}

        This code expires in 1 hour.

        If you did not request this, you can ignore this email.

        Best regards,
        © LearnPeak
        """

        sent = self.email_service.send_otp_email(
            to_email=current_email,
            subject="Verify your current email • LearnPeak",
            text_fallback=text_fallback,
            title="LearnPeak",
            header="Verify Your Current Email",
            main_text=(
                "To continue changing your email, please verify your current address with the code below."
            ),
            otp=otp,
            ignore_text="If you didn’t request an email change, you can safely ignore this email.",
            expiry_time="1 hour",
        )

        if not sent:
            return False, "Could not send verification email to your current address."

        return True, "Verification code sent to your current email."

    def verify_current_email(self, user_uid: str, otp: str) -> tuple[bool, str]:
        """Verify the current email OTP and return the result."""
        validation = self.otp_mgr.validate_otp(
            f"account_email_change/{user_uid}/current_email", otp
        )

        if validation is not True:
            return False, str(validation)

        return True, "Current email verified."

    def send_new_email_verification(
        self, user_uid: str, current_email: str, new_email: str
    ) -> tuple[bool, str]:
        """Send a verification OTP to the new email address."""
        new_email = (new_email or "").strip().lower()
        current_email = (current_email or "").strip().lower()

        if not new_email:
            return False, "New email is required."

        if new_email == current_email:
            return False, "The new email must be different from your current email."

        validation = self.signup_service.validate_email(new_email)
        if validation is not True:
            return False, validation

        otp_store_path = f"account_email_change/{user_uid}/new_email"
        otp = self.otp_mgr.generate_and_store_otp(otp_store_path)

        self.root_ref.child(f"account_email_change/{user_uid}/pending_new_email").set(
            new_email
        )

        text_fallback = f"""
        Hello,

        You requested to change your LearnPeak email address.

        Your verification code is: {otp}

        This code expires in 1 hour.

        If you did not make this change, please ignore this email.

        Best regards,
        © LearnPeak
        """

        sent = self.email_service.send_otp_email(
            to_email=new_email,
            subject="Verify your new email • LearnPeak",
            text_fallback=text_fallback,
            title="LearnPeak",
            header="Verify Your New Email",
            main_text=(
                "Use the verification code below to confirm the email you want to use for your LearnPeak account."
            ),
            otp=otp,
            ignore_text="If you didn’t request this change, you can safely ignore this email.",
            expiry_time="1 hour",
        )

        if not sent:
            return False, "Could not send verification email to the new address."

        return True, "Verification code sent to your new email."

    def verify_new_email(self, user_uid: str, otp: str) -> tuple[bool, str]:
        """Confirm the new email OTP and return the result."""
        validation = OTPManager(self.root_ref).validate_otp(
            f"account_email_change/{user_uid}/new_email", otp
        )

        if validation is not True:
            return False, str(validation)

        return True, "New email verified."

    def complete_email_change(
        self, user_uid: str, current_email: str, new_email: str
    ) -> tuple[bool, str]:
        """Apply the verified new email to the account and firebase indexes."""
        current_email = (current_email or "").strip().lower()
        new_email = (new_email or "").strip().lower()

        if not new_email:
            return False, "Email is required."

        if new_email == current_email:
            return True, "No changes made."

        validation = self.signup_service.validate_email(new_email)
        if validation is not True:
            return False, validation

        old_key = AuthUtils.normalize_email(current_email)
        new_key = AuthUtils.normalize_email(new_email)

        updates = {}
        if old_key:
            updates[f"email_index/{old_key}"] = None

        updates[f"users/{user_uid}/info/email"] = new_email
        updates[f"email_index/{new_key}"] = user_uid
        updates[f"account_email_change/{user_uid}"] = None

        self.root_ref.update(updates)
        return True, "Email updated"

    def delete_account(self, user_uid: str, username: str, email: str) -> bool:
        """Delete the user's database records and related indexes."""
        updates = {f"users/{user_uid}": None}

        if username:
            updates[f"username_index/{username}"] = None

        if email:
            normalized_email = AuthUtils.normalize_email(email)
            updates[f"email_index/{normalized_email}"] = None
            updates[f"login_otps/{normalized_email}"] = None
            updates[f"email_verifications/{normalized_email}"] = None
            updates[f"password_resets/{normalized_email}"] = None

        updates[f"account_email_change/{user_uid}"] = None

        self.root_ref.update(updates)
        return True
