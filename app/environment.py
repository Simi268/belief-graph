class DynamicAPIEnvironment:

    def __init__(self):

        self.api_version = "v1"

    def set_api_version(
        self,
        version: str
    ):

        self.api_version = version

    def get_api_version(self):

        return self.api_version

    def call_api(
        self,
        version: str
    ):

        if version != self.api_version:

            return {
                "success": False,
                "error": "API_VERSION_MISMATCH",
                "expected": self.api_version,
                "received": version
            }

        return {
            "success": True,
            "data": "customer-data"
        }