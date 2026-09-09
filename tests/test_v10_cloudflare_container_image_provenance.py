from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import apps.api.cloudflare_runtime as runtime


class CloudflareContainerImageProvenanceTests(unittest.TestCase):
    def test_container_image_source_sha_accepts_exact_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source-sha.txt"
            source.write_text(f"{'a' * 40}\n", encoding="ascii")
            self.assertEqual(runtime._container_image_source_sha(source), "a" * 40)

    def test_container_image_source_sha_rejects_missing_and_invalid_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source-sha.txt"
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_RUNTIME_IMAGE_SOURCE_SHA_REQUIRED",
            ):
                runtime._container_image_source_sha(source)
            source.write_text("not-a-sha\n", encoding="ascii")
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_RUNTIME_IMAGE_SOURCE_SHA_INVALID",
            ):
                runtime._container_image_source_sha(source)

    def test_container_source_route_precedes_generic_api_catchall(self) -> None:
        app = FastAPI()

        def catchall(path: str) -> JSONResponse:
            del path
            return JSONResponse({"detail": "catchall"}, status_code=404)

        app.add_api_route("/api/{path:path}", catchall, methods=["GET"])
        runtime._install_container_source_route(app, "a" * 40)

        response = TestClient(app).get(runtime._CONTAINER_SOURCE_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "image_source_sha": "a" * 40},
        )

    def test_container_source_route_rejects_invalid_sha(self) -> None:
        app = FastAPI()
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_RUNTIME_IMAGE_SOURCE_SHA_INVALID",
        ):
            runtime._install_container_source_route(app, "not-a-sha")


if __name__ == "__main__":
    unittest.main()
