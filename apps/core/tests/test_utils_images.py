"""Tests for the ``apps.core.utils.images`` module."""

from unittest import mock

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.core.utils.images import get_random_user_image, save_temporary_form_image

TEST_MEDIA_ROOT = "/tmp/django_template_test_media"


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ImagesUtilsTests(TestCase):
    """Tests for the image helper functions."""

    def setUp(self) -> None:
        self.saved_name: str | None = None

    def tearDown(self) -> None:
        if self.saved_name:
            default_storage.delete(self.saved_name)

    def test_save_temporary_form_image(self) -> None:
        """The uploaded image is stored under the temp folder."""
        upload = SimpleUploadedFile(
            "pic.png", b"image-content", content_type="image/png"
        )
        saved_name = save_temporary_form_image(upload)
        self.saved_name = saved_name
        self.assertTrue(saved_name.startswith("temp/temp_pic.png"))
        self.assertTrue(default_storage.exists(saved_name))

    @mock.patch("apps.core.utils.images.requests.get")
    def test_get_random_user_image_success(self, mock_get) -> None:
        """A successful request returns the avatar URL from the payload."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "results": [{"picture": {"large": "https://img/avatar.jpg"}}]
        }
        self.assertEqual(get_random_user_image(), "https://img/avatar.jpg")
        mock_get.assert_called_once_with("https://randomuser.me/api/")

    @mock.patch("apps.core.utils.images.requests.get")
    def test_get_random_user_image_error(self, mock_get) -> None:
        """A failed request returns None."""
        mock_get.return_value.status_code = 500
        self.assertIsNone(get_random_user_image())
