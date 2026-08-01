"""Custom exceptions for XHS API client."""


class XhsApiError(Exception):
    def __init__(self, message: str, code=None, response=None):
        super().__init__(message)
        self.code = code
        self.response = response

class NeedVerifyError(XhsApiError):
    def __init__(self, verify_type: str = "", verify_uuid: str = ""):
        super().__init__(f"Captcha required: type={verify_type}, uuid={verify_uuid}")

class SessionExpiredError(XhsApiError):
    def __init__(self):
        super().__init__("Session expired — please refresh cookies", code=-100)

class IpBlockedError(XhsApiError):
    def __init__(self):
        super().__init__("IP blocked by XHS — try a different network", code=300012)

class SignatureError(XhsApiError):
    def __init__(self):
        super().__init__("Signature verification failed", code=300015)

class UnsupportedOperationError(XhsApiError):
    def __init__(self, message: str):
        super().__init__(message, code="unsupported_operation")
