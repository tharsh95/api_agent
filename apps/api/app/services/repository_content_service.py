import base64
import binascii


class GitHubContentService:

    @staticmethod
    def decode_file_content(
        encoded_content: str,
    ) -> str | None:
        encoded_content = encoded_content.replace(
            "\n",
            "",
        )

        try:
            return base64.b64decode(
                encoded_content
            ).decode("utf-8")

        except (
            binascii.Error,
            UnicodeDecodeError,
        ):
            return None