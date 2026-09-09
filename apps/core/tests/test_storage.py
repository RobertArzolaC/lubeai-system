"""Tests for the ``apps.core.storage`` module."""

import os

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from apps.core.storage import CustomStorage

TEST_MEDIA_ROOT = "/tmp/django_template_test_media"


@override_settings(MEDIA_ROOT="/unused", MEDIA_URL="/media/")
class CustomStorageTests(SimpleTestCase):
    """Tests for the :class:`CustomStorage` storage backend."""

    def setUp(self) -> None:
        self.storage = CustomStorage()
        self.saved_name: str | None = None

    def tearDown(self) -> None:
        if self.saved_name:
            self.storage.delete(self.saved_name)

    def test_storage_location(self) -> None:
        """Files are stored under the uploads/images media folder."""
        self.assertTrue(self.storage.location.endswith("uploads/images/"))

    def test_storage_base_url(self) -> None:
        """The public base URL points to the uploads/images folder."""
        self.assertTrue(self.storage.base_url.endswith("uploads/images/"))

    def test_save_and_open(self) -> None:
        """Saving a file makes it available through the storage."""
        self.storage.location = os.path.join(TEST_MEDIA_ROOT, "uploads", "images")
        name = self.storage.save("probe.txt", ContentFile(b"storage-probe"))
        self.saved_name = name
        self.assertTrue(self.storage.exists(name))
        self.assertEqual(self.storage.open(name).read(), b"storage-probe")
