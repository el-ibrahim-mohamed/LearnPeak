COUNTRIES = {"Egypt": "egypt"}

EDUCATION = {"🏫 National": "national"}

GRADES = {
    "🎨 kG 1": "kg1",
    "🎨 KG 2": "kg2",
    "🎒 Primary 1": "prim1",
    "🎒 Primary 2": "prim2",
    "🎒 Primary 3": "prim3",
    "🎒 Primary 4": "prim4",
    "🎒 Primary 5": "prim5",
    "🎒 Primary 6": "prim6",
    "📓 Preparatory 1": "prep1",
    "📓 Preparatory 2": "prep2",
    "📓 Preparatory 3": "prep3",
    "🔬 Secondary 1": "sec1",
    "🔬 Secondary 2": "sec2",
    "🔬 Secondary 3": "sec3",
}

SUBJECTS = {
    "📖 English": "english",
    "🔢 Math": "math",
    "🔬 Science": "science",
    "📚 Arabic": "arabic",
    "🌍 Social Studies": "social_studies",
    "🕌 Islamic Religion": "islamic_religion",
    "🇩🇪 German": "german",
    "💻 ICT": "ict",
}

BOOK_PUBLISHERS = {
    "📗 El-Moasser": "el-moasser",
    "📙 El-Emtihan": "el-emtihan",
    "🏫 School Book": "school_book",
}

UNIT_OPTIONS = [1, 2, 3, 4]

LESSON_OPTIONS = [1, 2, 3, 4, 5, 6]

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
    GEMINI_MODELS_CODES["flash-lite-latest"],
    GEMINI_MODELS_CODES["3.1-flash-lite"],
    GEMINI_MODELS_CODES["flash-latest"],
    GEMINI_MODELS_CODES["3.6-flash"],
]

GEMINI_FLASH_FIRST = [
    GEMINI_MODELS_CODES["flash-latest"],
    GEMINI_MODELS_CODES["3.6-flash"],
    GEMINI_MODELS_CODES["flash-lite-latest"],
    GEMINI_MODELS_CODES["3.1-flash-lite"],
]