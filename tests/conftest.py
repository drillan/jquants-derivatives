from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import pytest

import jquants_derivatives
from jquants_derivatives import client, models


@pytest.fixture()
def cli():
    jquants_derivatives.database.db = Path(__file__).resolve().parent / "jquantsapi.db"

    class Client(TestCase):
        @patch("jquants_derivatives.Client")
        @client.cast_dataframe(models.IndexOption)
        def get_option_index_option(self, *args, **kwargs):
            return jquants_derivatives.database.load(
                "OPTION_INDEX_OPTION", "2023-01-04"
            )

    return Client()
