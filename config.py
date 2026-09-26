# ==========================================
# Constants
# ==========================================

COUNTRIES = {"Egypt": "egypt"}

EDUCATION = {"🏫 National": "national"}

GRADES = {
    "🎨 Primary 1": "prim1",
    "🎨 Primary 2": "prim2",
    "🎨 Primary 3": "prim3",
    "🎒 Primary 4": "prim4",
    "🎒 Primary 5": "prim5",
    "🎒 Primary 6": "prim6",
    "📓 Preparatory 1": "prep1",
    "📓 Preparatory 2": "prep2",
    "📓 Preparatory 3": "prep3",
}

SUBJECTS = {
    "📚 Arabic": "arabic",
    "📖 English": "english",
    "🔢 Math": "math",
    "🔬 Science": "science",
    "🌍 Social Studies": "social_studies",
}

GRADE_SUBJECTS = {
    "prim1": ["arabic", "english", "math"],
    "prim2": ["arabic", "english", "math"],
    "prim3": ["arabic", "english", "math"],
    "prim4": ["arabic", "english", "math", "science", "social_studies"],
    "prim5": ["arabic", "english", "math", "science", "social_studies"],
    "prim6": ["arabic", "english", "math", "science", "social_studies"],
    "prep1": ["arabic", "english", "math", "science", "social_studies"],
    "prep2": ["arabic", "english", "math", "science", "social_studies"],
    "prep3": ["arabic", "english", "math", "science", "social_studies"],
}

BOOK_PUBLISHERS = {
    "📙 El-Moasser": "el-moasser",
    "📗 El-Emtihan": "el-emtihan",
    "📘 Al-Adwaa": "al-adwaa",
    "📕 Selah El-Telmeez": "selah-el-telmeez",
}

UNIT_OPTIONS = [1, 2, 3, 4]

LESSON_OPTIONS = [1, 2, 3, 4]

CATEGORIES = {
    "📙 External Book": "external_book",
    "📝 Assessment Book": "assessments_book",
}

ENGLISH_CATEGORIES = {
    "📙 External Book": "external_book",
    "📝 Assessment Book": "assessments_book",
    "📚 AL": "al",
    "📖 AL Story": "al_story",
}

DEFAULT_PUBLISHERS = {
    "prim1": {
        "arabic": "selah-el-telmeez",
        "english": "el-moasser",
        "math": "el-moasser",
    },
    "prim2": {
        "arabic": "al-adwaa",
        "english": "el-moasser",
        "math": "el-moasser",
    },
    "prim3": {
        "arabic": "al-adwaa",
        "english": "el-moasser",
        "math": "el-moasser",
    },
    "prim4": {
        "arabic": "el-emtihan",
        "english": "el-moasser",
        "math": "el-moasser",
        "science": "el-moasser",
        "social_studies": "selah-el-telmeez",
    },
    "prim5": {
        "arabic": "al-adwaa",
        "english": "el-moasser",
        "math": "el-moasser",
        "science": "el-moasser",
        "social_studies": "selah-el-telmeez",
    },
    "prim6": {
        "arabic": "al-adwaa",
        "english": "el-moasser",
        "math": "el-moasser",
        "science": "el-moasser",
        "social_studies": "selah-el-telmeez",
    },
    "prep1": {
        "arabic": "el-emtihan",
        "english": "el-moasser",
        "math": "el-moasser",
        "science": "el-moasser",
        "social_studies": "el-emtihan",
    },
    "prep2": {
        "arabic": "el-emtihan",
        "english": "el-moasser",
        "math": "el-moasser",
        "science": "el-moasser",
        "social_studies": "el-emtihan",
    },
    "prep3": {
        "arabic": "el-emtihan",
        "english": "el-moasser",
        "math": "el-moasser",
        "science": "el-moasser",
        "social_studies": "el-emtihan",
    },
}

GEMINI_MODELS_CODES = {
    "flash-latest": "gemini-3.7-flash",
    "flash-lite-latest": "gemini-3.5-flash-lite",
    "3.7-flash": "gemini-3.7-flash",
    "3.6-flash": "gemini-3.6-flash",
    "3.5-flash": "gemini-3.5-flash",
    "3.5-flash-lite": "gemini-3.5-flash-lite",
    "3.1-flash-lite": "gemini-3.1-flash-lite",
    "2.5-flash": "gemini-2.5-flash",
    "2.5-flash-lite": "gemini-2.5-flash-lite",
}

GEMINI_LITE_FIRST = [
    GEMINI_MODELS_CODES["3.1-flash-lite"],
    GEMINI_MODELS_CODES["2.5-flash-lite"],
    GEMINI_MODELS_CODES["flash-latest"],
    GEMINI_MODELS_CODES["3.6-flash"],
]

GEMINI_FLASH_FIRST = [
    GEMINI_MODELS_CODES["flash-latest"],
    GEMINI_MODELS_CODES["3.6-flash"],
    GEMINI_MODELS_CODES["flash-lite-latest"],
    GEMINI_MODELS_CODES["3.1-flash-lite"],
]

EMBEDDING_VECTOR_SIZE = 384

# ==========================================
# UTILITY FUNCTIONS
# ==========================================


def get_subjects_for_grade(grade_key: str) -> dict:
    """Returns a filtered dict of {display_name: subject_code} for a specific grade."""
    allowed_keys = GRADE_SUBJECTS.get(grade_key, [])
    return {display: code for display, code in SUBJECTS.items() if code in allowed_keys}


def get_key_by_value(d: dict, value):
    """Reverse lookup: returns the key corresponding to a given value in a dictionary."""
    return next((k for k, v in d.items() if v == value), None)
