import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.document import create_document, set_public_permission

class TestUploader(unittest.TestCase):
    @patch('src.document.get_client')
    def test_create_document(self, mock_get_client):
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_response.data.document.document_id = "doc_token_123"
        mock_client.docx.v1.document.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Run
        token = create_document("Test Title")

        # Verify
        self.assertEqual(token, "doc_token_123")
        mock_client.docx.v1.document.create.assert_called_once()

    @patch('src.document.get_client')
    def test_set_permission(self, mock_get_client):
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.success.return_value = True
        mock_client.drive.v1.permission_public.patch.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Run
        result = set_public_permission("doc_token_123")

        # Verify
        self.assertTrue(result)
        mock_client.drive.v1.permission_public.patch.assert_called_once()

if __name__ == '__main__':
    unittest.main()
