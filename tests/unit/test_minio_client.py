import io
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import timedelta


class TestSingletonPattern:
    def test_singleton_returns_same_instance(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client1 = MinIOClient()
            client2 = MinIOClient()
            assert client1 is client2
        MinIOClient._instance = None

    def test_singleton_reset_creates_new_instance(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client1 = MinIOClient()
        MinIOClient._instance = None
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client2 = MinIOClient()
            assert client1 is not client2
        MinIOClient._instance = None


class TestUploadObject:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_upload_object_success(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.upload_object(
                "test-bucket", "test-key", b"hello world", "text/plain", 11
            )

            assert result["status"] == "success"
            assert result["bucket"] == "test-bucket"
            assert result["key"] == "test-key"
            assert result["size"] == 11
            mock_client.put_object.assert_called_once()

    def test_upload_object_no_client(self):
        from odap.infra.storage.minio_client import MinIOClient
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = None

            result = client.upload_object("bucket", "key", b"data")
            assert result["status"] == "error"

    def test_upload_object_auto_length(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            data = b"auto length data"
            result = client.upload_object("bucket", "key", data)
            assert result["status"] == "success"
            assert result["size"] == len(data)


class TestDownloadObject:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_download_object_success(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"downloaded data"
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_client.get_object.return_value = mock_response

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.download_object("bucket", "key")
            assert result["status"] == "success"
            assert result["data"] == b"downloaded data"
            assert result["size"] == len(b"downloaded data")

    def test_download_object_no_client(self):
        from odap.infra.storage.minio_client import MinIOClient
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = None

            result = client.download_object("bucket", "key")
            assert result["status"] == "error"


class TestGetPresignedUrl:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_get_presigned_url_success(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_client.presigned_get_object.return_value = "http://minio:9000/bucket/key?X-Amz-Signature=xxx"

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.get_presigned_url("bucket", "key")
            assert result["status"] == "success"
            assert "url" in result
            assert result["expires_seconds"] == 3600

    def test_get_presigned_url_custom_expiry(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_client.presigned_get_object.return_value = "http://minio:9000/bucket/key?X-Amz-Signature=xxx"

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.get_presigned_url("bucket", "key", expires=timedelta(minutes=30))
            assert result["status"] == "success"
            assert result["expires_seconds"] == 1800


class TestDeleteObject:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_delete_object_success(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.delete_object("bucket", "key")
            assert result["status"] == "success"
            mock_client.remove_object.assert_called_once_with("bucket", "key")

    def test_delete_object_no_client(self):
        from odap.infra.storage.minio_client import MinIOClient
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = None

            result = client.delete_object("bucket", "key")
            assert result["status"] == "error"


class TestEnsureBucket:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_ensure_bucket_creates_new(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.ensure_bucket("new-bucket")
            assert result["status"] == "success"
            assert result["created"] is True
            mock_client.make_bucket.assert_called_once_with("new-bucket")

    def test_ensure_bucket_already_exists(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.ensure_bucket("existing-bucket")
            assert result["status"] == "success"
            assert result["created"] is False
            mock_client.make_bucket.assert_not_called()


class TestListObjects:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_list_objects_success(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_obj = MagicMock()
        mock_obj.object_name = "file1.txt"
        mock_obj.size = 1024
        mock_obj.last_modified = None
        mock_obj.content_type = "text/plain"
        mock_obj.is_dir = False
        mock_client.list_objects.return_value = [mock_obj]

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.list_objects("bucket", prefix="prefix/")
            assert result["status"] == "success"
            assert result["count"] == 1
            assert result["objects"][0]["name"] == "file1.txt"

    def test_list_objects_with_prefix(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_client.list_objects.return_value = []

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.list_objects("bucket", prefix="docs/")
            assert result["status"] == "success"
            assert result["count"] == 0
            mock_client.list_objects.assert_called_once_with("bucket", prefix="docs/", recursive=True)


class TestUploadLargeFile:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_upload_large_file(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            large_data = b"x" * (5 * 1024 * 1024)
            result = client.upload_object("bucket", "large-file.bin", large_data, "application/octet-stream")
            assert result["status"] == "success"
            assert result["size"] == 5 * 1024 * 1024


class TestWorkspaceBucketIsolation:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_workspace_bucket_isolation(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            ws1_bucket = "ws-abc123"
            ws2_bucket = "ws-def456"

            result1 = client.ensure_bucket(ws1_bucket)
            result2 = client.ensure_bucket(ws2_bucket)

            assert result1["status"] == "success"
            assert result2["status"] == "success"
            assert mock_client.make_bucket.call_count == 2
            calls = mock_client.make_bucket.call_args_list
            assert calls[0][0][0] == ws1_bucket
            assert calls[1][0][0] == ws2_bucket


class TestErrorHandling:
    def setup_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def teardown_method(self):
        from odap.infra.storage.minio_client import MinIOClient
        MinIOClient._instance = None

    def test_s3_error_on_upload(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()

        try:
            from minio.error import S3Error
            mock_client.put_object.side_effect = S3Error(
                "NoSuchBucket", "The specified bucket does not exist", "resource", "request_id", "host_id", "response"
            )
        except ImportError:
            mock_client.put_object.side_effect = Exception("NoSuchBucket")

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.upload_object("nonexistent", "key", b"data")
            assert result["status"] == "error"

    def test_generic_error_on_download(self):
        from odap.infra.storage.minio_client import MinIOClient
        mock_client = MagicMock()
        mock_client.get_object.side_effect = ConnectionError("Connection refused")

        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = mock_client

            result = client.download_object("bucket", "key")
            assert result["status"] == "error"
            assert "Connection refused" in result["message"]

    def test_env_var_configuration(self):
        from odap.infra.storage.minio_client import MinIOClient
        import odap.infra.config_composer as cc_mod
        with patch.dict("os.environ", {
            "MINIO_ENDPOINT": "custom-minio:9000",
            "MINIO_ACCESS_KEY": "custom_key",
            "MINIO_SECRET_KEY": "custom_secret",
            "MINIO_SECURE": "true",
        }):
            # 重置 ConfigurationComposer 单例，使 get_config() 读取新环境变量
            cc_mod._global_composer = None
            client = MinIOClient()
            assert client._endpoint == "custom-minio:9000"
            assert client._access_key == "custom_key"
            assert client._secret_key == "custom_secret"
            assert client._secure is True
            # 清理：重置单例和 MinIOClient 以免影响其他测试
            cc_mod._global_composer = None

    def test_available_property_no_client(self):
        from odap.infra.storage.minio_client import MinIOClient
        with patch.dict("os.environ", {"MINIO_ENDPOINT": "localhost:9000"}):
            client = MinIOClient()
            client._client = None
            assert client.available is False
