"""Directed checks for the pilot explicit image / installed-payload selection.

Round-3 audit R5: the pilot must be able to select the new scaled image and its
built-in payload explicitly, verify the immutable image ID before any workload,
keep the old default (current-image.json) compatible, and never pass a host
absolute path as the container payload argument. These checks exercise command
construction, identity rejection, container-vs-host payload paths and mount
expectations WITHOUT starting perf record or DevKit.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analysis/docops"))

import pilot

SCALED_IMAGE_ID = "sha256:6b32b0a53741a42562ca3e93894139c34cf774a214b7995e44af0cec61f14967"
SCALED_TAG = "docops-replay:openeuler-scaled"
CANDIDATE_TAG = "docops-replay:openeuler-unified-candidate-04"
CANDIDATE_ID = "sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164"


class TestResolveImage(unittest.TestCase):
    def test_resolves_scaled_tag_to_immutable_id(self):
        image = pilot.resolve_image(SCALED_TAG)
        self.assertEqual(image["Id"], SCALED_IMAGE_ID)

    def test_resolves_immutable_id_directly(self):
        image = pilot.resolve_image(SCALED_IMAGE_ID)
        self.assertEqual(image["Id"], SCALED_IMAGE_ID)

    def test_expected_id_mismatch_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            pilot.resolve_image(SCALED_TAG, expected_id="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
        self.assertIn("expected image id", str(ctx.exception))

    def test_expected_id_match_passes(self):
        image = pilot.resolve_image(SCALED_TAG, expected_id=SCALED_IMAGE_ID)
        self.assertEqual(image["Id"], SCALED_IMAGE_ID)


class TestBuildCreate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__import__("tempfile").mkdtemp())

    def test_installed_payload_uses_container_path(self):
        create, expected_mounts, payload_arg = pilot.build_create(
            "016-u100", 3, "perf", SCALED_IMAGE_ID, self.tmp / "src", self.tmp / "out",
            installed_payload="/opt/docops/scaling/payload-all",
            workload_timeout=7200, step_timeout=3600)
        self.assertEqual(payload_arg, "/opt/docops/scaling/payload-all")
        # no host payload mount (only the measurement source and results are mounted)
        self.assertFalse(any("target=/opt/docops/scaling/payload" in arg for arg in create))
        # installed payload implies no host replay/compile mounts
        self.assertIn("--payload", create)
        self.assertIn("/opt/docops/scaling/payload-all", create)
        self.assertEqual(expected_mounts, {"/opt/docops-measurement", "/results"})
        self.assertNotIn("/opt/docops/scaling/payload", expected_mounts)

    def test_host_payload_mount_kept_for_backward_compat(self):
        host = ROOT / "docops/scaling/payload-word-pdf"
        create, expected_mounts, payload_arg = pilot.build_create(
            "003-u100", 1, "topdown", CANDIDATE_ID, self.tmp / "src", self.tmp / "out",
            payload=host, workload_timeout=7200, step_timeout=3600,
            host_replay=ROOT / "docops/replay.py", host_compile=ROOT / "docops/compile.py")
        self.assertEqual(payload_arg, "/opt/docops/scaling/payload")
        self.assertTrue(any("docops/scaling/payload-word-pdf" in arg for arg in create))
        self.assertTrue(any("target=/opt/docops/scaling/payload" in arg for arg in create))
        self.assertTrue(any("target=/opt/docops/replay.py" in arg for arg in create))
        self.assertIn("/opt/docops/scaling/payload", expected_mounts)

    def test_no_payload_no_payload_arg(self):
        create, expected_mounts, payload_arg = pilot.build_create(
            "031", 10, "perf", CANDIDATE_ID, self.tmp / "src", self.tmp / "out",
            workload_timeout=600, step_timeout=1200)
        self.assertIsNone(payload_arg)
        self.assertNotIn("--payload", create)

    def test_both_payloads_rejected(self):
        with self.assertRaises(ValueError):
            pilot.build_create("016-u100", 1, "perf", SCALED_IMAGE_ID,
                               self.tmp / "src", self.tmp / "out",
                               payload=ROOT / "docops/scaling/payload-word-pdf",
                               installed_payload="/opt/docops/scaling/payload-all")

    def test_docker_option_order(self):
        create, _expected, _payload_arg = pilot.build_create(
            "016-u100", 3, "topdown", SCALED_IMAGE_ID, self.tmp / "src", self.tmp / "out",
            installed_payload="/opt/docops/scaling/payload-all")
        self.assertEqual(create[:4], pilot.DOCKER + ["create"])
        self.assertIn("--network", create)
        self.assertIn("--cpuset-cpus", create)
        # image id comes after all container options, before the entry
        self.assertIn(SCALED_IMAGE_ID, create)
        self.assertIn("--entrypoint", create)
        # entrypoint python3 ... capture.py after the image id
        idx_entry = create.index("--entrypoint")
        idx_image = create.index(SCALED_IMAGE_ID)
        self.assertLess(idx_entry, idx_image)


class TestLaunchIdentity(unittest.TestCase):
    """launch() resolves and verifies the image before any workload; a mismatch
    is rejected up front. We only exercise the resolution path (no collection
    is started for the mismatch case)."""

    def test_expected_id_mismatch_rejected_before_launch(self):
        with self.assertRaises(ValueError) as ctx:
            pilot.launch("016-u100", 1, ["perf"], image_ref=SCALED_TAG,
                         expected_image_id="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
        self.assertIn("expected image id", str(ctx.exception))



class TestContainerNaming(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__import__("tempfile").mkdtemp())

    def test_repeat_calls_get_unique_container_names(self):
        # Retained containers must never collide; no '-tmp' constant name and no
        # reliance on deleting an old container.
        names = []
        for _ in range(3):
            create, _expected, _arg = pilot.build_create(
                "016-u100", 1, "perf", SCALED_IMAGE_ID,
                self.tmp / "src", self.tmp / "out",
                installed_payload="/opt/docops/scaling/payload-all")
            name = create[create.index("--name") + 1]
            self.assertFalse(name.endswith("-tmp"))
            names.append(name)
        self.assertEqual(len(set(names)), 3)

    def test_explicit_container_name_preserved(self):
        create, _expected, _arg = pilot.build_create(
            "016-u100", 1, "perf", SCALED_IMAGE_ID, self.tmp / "src", self.tmp / "out",
            container_name="docops-perf-016-u100-attempt-7")
        self.assertEqual(create[create.index("--name") + 1],
                         "docops-perf-016-u100-attempt-7")

if __name__ == "__main__":
    unittest.main()
