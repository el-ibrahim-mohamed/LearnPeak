import streamlit as st
import time
from services.account.settings import AccountSettingsService
from config import *

# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------

st.set_page_config(
    page_title="Settings - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

root_ref = st.session_state.get("root_ref")
cookies = st.session_state.get("cookies")
user: dict = st.session_state.get("user", {})

if not user:
    st.warning("Please sign in to manage your account settings.")
    st.stop()

sender_email = st.secrets["smtp"]["SENDER_EMAIL"]
sender_app_password = st.secrets["smtp"]["SENDER_APP_PASSWORD"]
settings_service = AccountSettingsService(root_ref, sender_email, sender_app_password)

if "settings_email_step" not in st.session_state:
    st.session_state["settings_email_step"] = "idle"
if "settings_email_new" not in st.session_state:
    st.session_state["settings_email_new"] = user.get("email", "")
if "trigger_email_dialog" not in st.session_state:
    st.session_state["trigger_email_dialog"] = False

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------


def update_session_user(field: str, value):
    """Keep the active session user in sync with the database."""
    if "user" in st.session_state:
        st.session_state["user"][field] = value


def save_info_field(field: str, value: str):
    """Wrapper around the backend info updater."""
    result = settings_service.update_user_info(user["uid"], field, value)
    if result[0]:
        update_session_user(field, (value or "").strip())
    return result


def save_username_field(username: str):
    """Wrapper around the backend username updater."""
    result = settings_service.update_username(
        user["uid"], username, user.get("username", "")
    )
    if result[0]:
        update_session_user("username", (username or "").strip())
    return result


def sign_out_user():
    """Clear the auth cookies and sign the user out."""
    auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
    user_uid_cookie_name = st.secrets["cookies"]["USER_UID_NAME"]

    cookies[auth_cookie_name] = ""
    cookies[user_uid_cookie_name] = ""
    cookies.save()

    st.session_state.pop("user", None)
    if st.user.is_logged_in:
        st.logout()
    st.switch_page("pages/home.py")


def delete_user_account():
    """Delete the current user record and clear their cookies."""
    settings_service.delete_account(
        user["uid"],
        (user.get("username") or "").strip(),
        (user.get("email") or "").strip().lower(),
    )

    auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
    user_uid_cookie_name = st.secrets["cookies"]["USER_UID_NAME"]

    cookies[auth_cookie_name] = ""
    cookies[user_uid_cookie_name] = ""
    cookies.save()

    st.session_state.pop("user", None)

    st.success("Your account has been deleted.")
    time.sleep(1.2)

    if st.user.is_logged_in:
        st.logout()
    st.switch_page("pages/home.py")


def get_key_by_value(d: dict, value):
    return next((k for k, v in d.items() if v == value), None)


# ---------------------------------------------------------
# MASTER DIALOG (CONDITIONAL STEPS)
# ---------------------------------------------------------


@st.dialog("Change Email Address")
def dialog_email_flow():
    """Single dialog managing all 3 steps based on settings_email_step."""
    step = st.session_state.get("settings_email_step", "verify_current_email")

    # STEP 1: Verify Current Email
    if step == "verify_current_email":
        st.write(
            f"We'll send a verification code to your current email: **{user.get('email', '')}**"
        )
        st.caption("This confirms your identity before we make any changes.")

        if st.session_state.get("settings_email_code_sent"):
            code = st.text_input(
                "Enter verification code",
                key="settings_dialog_current_code",
                max_chars=6,
                placeholder="000000",
            )

            # ---------------------------------------------------------
            # RESEND CODE (STATIC COOLDOWN)
            # ---------------------------------------------------------

            RESEND_COOLDOWN = 30

            if st.button("\u00a0:blue[Resend Code]", type="tertiary"):
                last_sent = st.session_state.get("last_resend_time", 0)
                elapsed = time.time() - last_sent

                if elapsed < RESEND_COOLDOWN:
                    remaining = int(RESEND_COOLDOWN - elapsed)
                    st.toast(
                        f"Please wait :red[{remaining}s] before requesting a new code.",
                        icon="⏳",
                    )
                else:
                    st.session_state["last_resend_time"] = time.time()
                    ok, message = settings_service.send_current_email_verification(
                        user["uid"], user.get("email", "")
                    )
                    if ok:
                        st.toast("Verification code resent!", icon="📩")
                    else:
                        st.error(message)

            error_ph = st.empty()

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verify code", use_container_width=True, type="primary"):
                    ok, message = settings_service.verify_current_email(
                        user["uid"], code
                    )
                    if ok:
                        st.session_state["settings_email_step"] = "enter_new_email"
                        st.session_state["settings_email_current_verified"] = True
                        st.session_state["trigger_email_dialog"] = True
                        st.rerun()
                    else:
                        error_ph.error(message)
            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state["settings_email_step"] = "idle"
                    st.session_state["settings_email_code_sent"] = False
                    st.rerun()

        else:
            if st.button(
                "Send verification code",
                use_container_width=True,
                type="primary",
            ):
                ok, message = settings_service.send_current_email_verification(
                    user["uid"], user.get("email", "")
                )
                if ok:
                    st.session_state["settings_email_code_sent"] = True
                    st.session_state["last_resend_time"] = time.time()
                    st.session_state["trigger_email_dialog"] = True
                    st.success("Verification code sent!")
                    st.rerun()
                else:
                    st.error(message)

    # STEP 2: Enter New Email
    elif step == "enter_new_email":
        st.write(
            "Enter the email address you'd like to use for your LearnPeak account."
        )
        current_email = user.get("email", "")
        new_email = st.text_input(
            "New email address",
            value=st.session_state.get("settings_email_new", ""),
            key="settings_dialog_new_email",
            placeholder=current_email,
        )
        st.session_state["settings_email_new"] = new_email
        error_ph = st.empty()

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Send verification code",
                use_container_width=True,
                type="primary",
            ):
                if not new_email.strip():
                    error_ph.error("Please enter a new email address.")
                elif new_email.strip().lower() == current_email.lower():
                    error_ph.error(
                        "The new email must be different from your current email."
                    )
                else:
                    ok, message = settings_service.send_new_email_verification(
                        user["uid"], current_email, new_email
                    )
                    if ok:
                        st.session_state["last_resend_time"] = time.time()
                        st.session_state["settings_email_step"] = "verify_new_email"
                        st.session_state["settings_email_new"] = (
                            new_email.strip().lower()
                        )
                        st.session_state["trigger_email_dialog"] = True
                        st.rerun()
                    else:
                        error_ph.error(message)
        with col2:
            if st.button("Back", use_container_width=True):
                st.session_state["settings_email_step"] = "verify_current_email"
                st.session_state["settings_email_code_sent"] = True
                st.session_state["trigger_email_dialog"] = True
                st.rerun()

    # STEP 3: Verify New Email
    elif step == "verify_new_email":
        new_email = st.session_state.get("settings_email_new", user.get("email", ""))
        st.write(f"A verification code was sent to: **{new_email}**")
        st.caption("Enter the code to confirm your new email address.")

        code = st.text_input(
            "Enter verification code",
            key="settings_dialog_new_code",
            placeholder="000000",
        )

        # ---------------------------------------------------------
        # RESEND CODE (STATIC COOLDOWN)
        # ---------------------------------------------------------

        RESEND_COOLDOWN = 30

        if st.button("\u00a0:blue[Resend Code]", type="tertiary"):
            last_sent = st.session_state.get("last_resend_time", 0)
            elapsed = time.time() - last_sent

            if elapsed < RESEND_COOLDOWN:
                remaining = int(RESEND_COOLDOWN - elapsed)
                st.toast(
                    f"Please wait :red[{remaining}s] before requesting a new code.",
                    icon="⏳",
                )
            else:
                st.session_state["last_resend_time"] = time.time()
                ok, message = settings_service.send_new_email_verification(
                    user["uid"], current_email, new_email
                )
                if ok:
                    st.toast("Verification code resent!", icon="📩")
                else:
                    st.error(message)

        status_ph = st.empty()

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Verify and save email",
                use_container_width=True,
                type="primary",
            ):
                if not code.strip():
                    status_ph.error("Please enter the verification code.")
                else:
                    ok, message = settings_service.verify_new_email(user["uid"], code)
                    if not ok:
                        status_ph.error(message)
                    else:
                        new_email_val = st.session_state.get(
                            "settings_email_new", user.get("email", "")
                        )
                        ok, message = settings_service.complete_email_change(
                            user["uid"], user.get("email", ""), new_email_val
                        )
                        if ok:
                            update_session_user("email", new_email_val.strip().lower())
                            st.session_state["settings_email_step"] = "idle"
                            st.session_state["settings_email_code_sent"] = False
                            st.session_state["settings_email_current_verified"] = False

                            status_ph.success("Email updated successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            status_ph.error(message)
        with col2:
            if st.button("Back", use_container_width=True):
                st.session_state["settings_email_step"] = "enter_new_email"
                st.session_state["trigger_email_dialog"] = True
                st.rerun()


# ---------------------------------------------------------
# SETTINGS UI
# ---------------------------------------------------------

st.title("⚙️ Settings", anchor=False)
st.caption("Manage your profile, account, and security settings.")

info_tab, account_tab = st.tabs(["ℹ️ Info", "👤 Account"])

with info_tab:
    # --- PROFILE INFO SECTION ---
    st.subheader("Profile info", icon="📋")

    with st.container(border=True):
        country_options = list(COUNTRIES.keys())
        current_country = user.get("country", "")
        current_country_key = get_key_by_value(COUNTRIES, current_country)
        country_index = (
            country_options.index(current_country_key)
            if current_country_key in country_options
            else 0
        )
        country = st.selectbox(
            "🌍 Country",
            options=country_options,
            index=country_index,
            key="settings_country",
            placeholder="Choose your country",
        )
        if current_country_key and country != current_country_key:
            ok, message = save_info_field("country", COUNTRIES[country])
            if ok:
                st.toast("Country saved.", icon="✅")
            else:
                st.warning(message)

        education_options = list(EDUCATION.keys())
        current_education_value = user.get("education", "")
        current_education_key = get_key_by_value(EDUCATION, current_education_value)
        education_index = (
            education_options.index(current_education_key)
            if current_education_key in education_options
            else 0
        )
        education = st.selectbox(
            "🎓 Education System",
            options=education_options,
            index=education_index,
            key="settings_education",
            placeholder="Choose your education",
        )
        if current_education_key and education != current_education_key:
            ok, message = save_info_field("education", EDUCATION[education])
            if ok:
                st.toast("Education system saved.", icon="✅")
            else:
                st.warning(message)

        grade_options = list(GRADES.keys())
        current_grade_value = user.get("grade", "")
        current_grade_key = get_key_by_value(GRADES, current_grade_value)
        grade_index = (
            grade_options.index(current_grade_key)
            if current_grade_key in grade_options
            else 0
        )
        grade = st.selectbox(
            "Grade",
            options=grade_options,
            index=grade_index,
            key="settings_grade",
            placeholder="Choose your grade",
        )
        if current_grade_key and grade != current_grade_key:
            ok, message = save_info_field("grade", GRADES[grade])
            if ok:
                st.toast("Grade saved.", icon="✅")
            else:
                st.warning(message)

    # --- PREFERRED PUBLISHERS SECTION ---

    user_grade = user.get("grade")
    current_user_pubs = user.get("preferred_book_publishers", {})

    # Fetch available publishers for user's grade
    with st.spinner("Loading..."):
        available_pubs_node = (
            root_ref.child("available_publishers").child(user_grade).get() or {}
        )

    all_subjects = GRADE_SUBJECTS[user_grade]

    st.markdown("### 📚 Preferred Publishers")

    # Styled container for the section
    with st.container(border=True):
        st.caption(
            "Customize your preferred publisher for each subject to refine search results."
        )

        updated_publishers = {}

        # 2-column or 1-column layout inside container
        cols = st.columns(2)

        for idx, subject in enumerate(all_subjects):
            col = cols[idx % 2]

            # Get raw code list from DB for this grade/subject, e.g., ["el-moasser", "el-emtihan"]
            available_codes = available_pubs_node.get(subject, [])

            # Map codes to UI labels for st.selectbox
            reversed_book_pubs = {value: key for key, value in BOOK_PUBLISHERS.items()}

            available_ui_labels = [
                reversed_book_pubs[code]
                for code in available_codes
                if code in reversed_book_pubs
            ]

            # Determine current selected code and map to UI label default
            current_code = current_user_pubs.get(subject, "")
            default_ui_label = reversed_book_pubs.get(current_code, None)

            # Calculate default index
            default_index = 0
            if default_ui_label and default_ui_label in available_ui_labels:
                default_index = available_ui_labels.index(default_ui_label)

            with col:
                subject_display_name = get_key_by_value(SUBJECTS, subject)

                if available_ui_labels:
                    selected_label = st.selectbox(
                        label=f"{subject_display_name}",
                        options=available_ui_labels,
                        index=default_index,
                        key=f"pub_select_{subject}",
                    )
                    # Store converted code back
                    updated_publishers[subject] = BOOK_PUBLISHERS[selected_label]
                else:
                    st.text_input(
                        label=f"{subject_display_name}",
                        value="No publishers available",
                        disabled=True,
                        key=f"pub_disabled_{subject}",
                    )

        " "
        if st.button(
            "Save Preferred Publishers", type="primary", use_container_width=True
        ):
            # Update user's preferred_book_publishers node directly
            root_ref.child(
                f"users/{user["uid"]}/info/preferred_book_publishers"
            ).update(updated_publishers)
            st.toast("Publisher preferences updated successfully!", icon="✅")

        "---"
        st.caption("Can't find your book or publisher in the list?")
        if st.button("🔍 Request Missing Book"):
            st.switch_page("pages/added_books.py")

with account_tab:
    st.subheader("Account settings", icon="⚙️")

    with st.container(border=True):
        st.write("Manage how your LearnPeak account is identified and secured.")

        col1, col2 = st.columns([0.7, 0.3], vertical_alignment="bottom")

        col1.text_input(
            "Email",
            value=user.get("email", ""),
            disabled=True,
        )

        if col2.button("✉️ Change email", use_container_width=True):
            st.session_state["settings_email_step"] = "verify_current_email"
            st.session_state["settings_email_code_sent"] = False
            st.session_state["trigger_email_dialog"] = True
            st.rerun()

        # One-shot trigger check
        if st.session_state.get("trigger_email_dialog"):
            st.session_state["trigger_email_dialog"] = False  # Instantly consume flag
            dialog_email_flow()

        " "

        username = st.text_input(
            "Username",
            value=user.get("username", ""),
            key="settings_username",
        )
        if username != (user.get("username") or ""):
            ok, message = save_username_field(username)
            if ok:
                st.toast("Username saved.", icon="✅")
            else:
                st.warning(message)
                st.session_state["settings_username"] = user.get("username") or ""

        " "

        if st.button("🚪 Sign out", use_container_width=True, type="secondary"):
            sign_out_user()

    st.subheader("⚠️ Danger zone")

    with st.container(border=True):
        st.warning(
            "Deleting your account permanently removes your profile and saved learning data."
        )

        if st.button("🗑️ Delete my account", use_container_width=True, type="primary"):
            if st.session_state.get("confirm_delete_account"):
                delete_user_account()
            else:
                st.session_state["confirm_delete_account"] = True
                st.warning("Press again to confirm permanent deletion.")

        if st.session_state.get("confirm_delete_account"):
            st.caption("This action cannot be undone.")
