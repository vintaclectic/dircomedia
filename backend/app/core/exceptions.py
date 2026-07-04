from fastapi import HTTPException


class NotFoundError(HTTPException):
    def __init__(self, resource: str, id: str):
        super().__init__(status_code=404, detail=f"{resource} '{id}' not found")


class GenerationError(Exception):
    def __init__(self, message: str, provider: str = None):
        self.provider = provider
        super().__init__(message)


class DistributionError(Exception):
    def __init__(self, message: str, platform: str = None):
        self.platform = platform
        super().__init__(message)
