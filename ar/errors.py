class ARServiceError(Exception):
    """Base exception for ARService"""


class SketchfabError(ARServiceError):
    pass


class SketchfabAuthError(SketchfabError):
    pass


class SketchfabDownloadError(SketchfabError):
    pass


class GeminiError(ARServiceError):
    pass


class GitHubHostingError(ARServiceError):
    pass

