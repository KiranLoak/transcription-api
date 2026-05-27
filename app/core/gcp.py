"""Google Cloud credential helpers."""

from __future__ import annotations

import json
import os
import tempfile

from app.core.settings import settings


def setup_gcp_credentials() -> None:
    """
    Render deployment:
    Creates temporary credentials file from env variable.

    Local development:
    Uses existing GOOGLE_APPLICATION_CREDENTIALS path.
    """

    # Already configured locally
    if settings.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(
        settings.GOOGLE_APPLICATION_CREDENTIALS
    ):
        return

    # Render JSON env variable
    if settings.GCP_SERVICE_ACCOUNT_JSON:
        creds_data = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON)

        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
        )

        json.dump(creds_data, temp_file)
        temp_file.close()

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_file.name
