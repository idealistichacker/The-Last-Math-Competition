"""Offline safety-contract tests for the contribution coordinator.

Fixtures are synthetic, not real proofs/reviews. Network, credentials and child
processes are denied by default. Publication and toolchain execution are mocked;
one index regression uses real Git exclusively in a temporary repository.
Known defects remain ordinary failing tests, never expectedFailure.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import types
import unittest
from unittest import mock
import urllib.error

# Avoid producing an import cache in scripts/, which belongs to another worker.
SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "contributor.py"
c = types.ModuleType("contributor_under_test")
c.__file__ = str(SOURCE)
exec(compile(SOURCE.read_text(encoding="utf-8-sig"), str(SOURCE), "exec"), c.__dict__)
REAL_RUN = subprocess.run
CID = "00000000427"
OTHER_ID = "00000000013"
SUBMISSION = "idealistichacker_submission_20260915060000"
RELATIVE = f"solutions/{CID}/{SUBMISSION}"
BLOB, NEW_BLOB = "a" * 40, "b" * 40
PIN = "4.33.1"
THEOREM = "Submission.refutation"
PDF = b"%PDF-1.7\nsynthetic unit-test fixture, not a compiled proof\n%%EOF\n"


class OfflineCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.urlopen = self.patch(c.urllib.request, "urlopen", side_effect=AssertionError("Real HTTP forbidden"))
        self.patch(socket, "create_connection", side_effect=AssertionError("Real sockets forbidden"))
        self.process = self.patch(c.subprocess, "run", side_effect=AssertionError("Unexpected real subprocess"))
        self.credentials = self.patch(c, "token_from_helper", side_effect=AssertionError("Real credentials forbidden"))

    def patch(self, target, name, **kwargs):
        patcher = mock.patch.object(target, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result


class FixtureCase(OfflineCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory(prefix="tlmc-unittest-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / RELATIVE
        self.path.mkdir(parents=True)
        self.common = self.root / "common-git"
        self.common.mkdir()
        self.source = self.root / "conjectures" / f"{CID}.md"
        self.source.parent.mkdir()
        self.source.write_text("Synthetic English statement.\n中文测试题面。\n", encoding="utf-8")
        self.write("README.md", "Synthetic fixture, not a genuinely reviewed mathematical solution.\n")
        self.write("main.tex", "\\documentclass{article}\\begin{document}Fixture\\end{document}\n")
        (self.path / "main.pdf").write_bytes(PDF)
        self.write("reproduce.py", "print('synthetic fixture only')\n")
        self.write("lean4/lean-toolchain", f"leanprover/lean4:v{PIN}\n")
        self.write("lean4/lakefile.toml", 'name = "fixture"\n[[lean_lib]]\nname = "Main"\n')
        self.write("lean4/Main.lean", "namespace Submission\ntheorem refutation : True := by trivial\nend Submission\n")
        self.write("lean4/Check.lean", f"import Main\n#print axioms {THEOREM}\n")
        self.manifest = {
            "version": 1, "id": CID, "solver": c.OWNER, "verdict": "disproved",
            "title": "synthetic regression fixture", "implementation_agent": "implementation-agent",
            "source_sha256": hashlib.sha256(self.source.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), "source_git_blob": BLOB,
            "statement_alignment": "Synthetic alignment evidence for unit testing only.",
            "formal_scope": "Synthetic formal scope, not actual mathematical verification.",
            "limitations": "External verification in this fixture is mocked, not executed.",
            "theorems": [THEOREM],
        }
        self.write_json("submission.json", self.manifest)
        self.review = {"verdict": "pass", "reviewer": "independent-review-agent",
                       "checks": {key: True for key in ("statement_alignment", "mathematics", "lean_bridge", "reproduction", "pdf_visual")}}
        self.resign_review()
        self.git = self.patch(c, "git", side_effect=self.fixture_git)
        self.runner = self.patch(c, "run", side_effect=self.fake_run)
        self.axiom_output = f"'{THEOREM}' does not depend on any axioms"
        self.lean_version = f"Lean (version {PIN}, x86_64, Release)"
        self.compiled_pdf = PDF
        self.mutate_on_reproduce = None

    def fixture_git(self, root, *args):
        if args == ("rev-parse", "--git-common-dir"):
            return str(self.common)
        if args == ("rev-parse", "--show-toplevel"):
            return str(root)
        if args[0] == "hash-object":
            return BLOB
        raise AssertionError(f"Unexpected mocked Git call: {args!r}")

    def write(self, relative, text):
        path = self.path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_json(self, relative, value):
        return self.write(relative, json.dumps(value, ensure_ascii=False))

    def resign_review(self):
        self.review["content_sha256"] = c.content_hash(self.path)
        self.write_json("review.json", self.review)

    def update_manifest(self, **changes):
        self.manifest.update(changes)
        self.write_json("submission.json", self.manifest)
        self.resign_review()

    def fake_run(self, args, cwd, timeout=300):
        args = [str(arg) for arg in args]
        if args[1:] == ["env", "lean", "--version"]:
            self.verified_lake_path = args[0]
            return self.lean_version
        if args[1:2] == ["reproduce.py"]:
            self.assertIn("--lake", args[2:])
            self.assertEqual(args.count("--lake"), 1)
            lake_index = args.index("--lake", 2) + 1
            self.assertLess(lake_index, len(args), "--lake requires a value")
            self.assertTrue(args[lake_index].strip(), "--lake cannot be empty")
            self.assertEqual(args[lake_index], self.verified_lake_path)
            self.assertEqual(timeout, 300)
            if self.mutate_on_reproduce:
                self.mutate_on_reproduce()
            return "Synthetic reproduction output"
        if args[1:] in (["build"], ["build", "Main"], ["env", "lean", "Main.lean"]):
            return "Synthetic compilation output"
        if args[1:] == ["env", "lean", "Check.lean"]:
            return self.axiom_output
        if len(args) == 4 and args[1] == "--outdir" and args[3] == "main.tex":
            out = Path(args[2])
            out.mkdir(parents=True, exist_ok=True)
            if self.compiled_pdf is not None:
                (out / "main.pdf").write_bytes(self.compiled_pdf)
            return "Synthetic PDF compilation output"
        raise AssertionError(f"Unexpected mocked command: {args!r}")

    def validate(self, execute=False):
        return c.validate(self.root, RELATIVE, "mock-lake", "mock-tectonic", execute=execute)

    def symlink(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except NotImplementedError as exc:
            self.skipTest(f"Symlinks unsupported: {exc}")
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314 or exc.errno in (1, 13, 38, 95):
                self.skipTest(f"Host does not allow symlinks: {exc}")
            raise
        self.addCleanup(lambda: link.unlink(missing_ok=True))


class PaginationTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.api = c.GitHub("synthetic-token")
        self.request = self.patch(self.api, "request")

    def test_empty_first_page_stops(self):
        self.request.return_value = []
        self.assertEqual(self.api.pages("/items"), [])
        self.request.assert_called_once_with("/items?per_page=100&page=1")

    def test_full_page_tail_and_existing_query(self):
        first, tail = list(range(100)), [100, 101]
        self.request.side_effect = [first, tail]
        self.assertEqual(self.api.pages("/items?state=all"), first + tail)
        self.assertEqual(self.request.call_args_list, [mock.call("/items?state=all&per_page=100&page=1"),
                                                     mock.call("/items?state=all&per_page=100&page=2")])

    def test_exact_multiple_requires_empty_sentinel_page(self):
        self.request.side_effect = [list(range(100)), []]
        self.assertEqual(len(self.api.pages("/items")), 100)
        self.assertEqual(self.request.call_count, 2)

    def test_non_array_responses_fail_closed(self):
        for response in ({"items": []}, {"message": "rate limited"}, None, "[]"):
            self.request.return_value = response
            with self.subTest(response=response), self.assertRaises(c.GateError):
                self.api.pages("/items")

    def test_later_page_error_cannot_return_partial_success(self):
        self.request.side_effect = [list(range(100)), c.GateError("rate limited")]
        with self.assertRaises(c.GateError):
            self.api.pages("/items")
        self.assertEqual(self.request.call_count, 2)

    def test_cap_reached_is_an_error_not_truncated_success(self):
        self.request.return_value = list(range(100))
        with self.assertRaises(c.GateError):
            self.api.pages("/items")
        self.assertEqual(self.request.call_count, 100)


class HttpBoundaryTests(OfflineCase):
    def test_absolute_and_network_relative_routes_rejected(self):
        for route in ("https://example.invalid/token", "//example.invalid/token", "repos/anything"):
            with self.subTest(route=route), self.assertRaises(c.GateError):
                c.GitHub("synthetic-token").request(route)
        self.urlopen.assert_not_called()

    def test_rate_limit_not_retried_and_secrets_not_in_error(self):
        secret = "synthetic-token-must-not-appear"
        self.urlopen.side_effect = urllib.error.HTTPError("https://api.github.com/user", 429,
                                                          "private server message", {}, io.BytesIO(secret.encode()))
        with self.assertRaises(c.GateError) as caught:
            c.GitHub(secret).request("/user")
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn("private server message", str(caught.exception))
        self.assertEqual(self.urlopen.call_count, 1)

    def test_refresh_failure_never_overwrites_complete_snapshot(self):
        api = mock.Mock()
        api.pages.side_effect = [[{"number": 1}], c.GateError("second endpoint failed")]
        save = self.patch(c, "save")
        with self.assertRaises(c.GateError):
            c.refresh(Path("unused"), api)
        save.assert_not_called()


class DuplicateTests(OfflineCase):
    def test_leading_zeros_and_repeated_mentions(self):
        item = {"title": f"Disproof {CID}", "body": f"solutions/{CID}/proof; {OTHER_ID}; {CID}"}
        self.assertEqual(c.mentioned_ids(item), {CID, OTHER_ID})

    def test_longer_and_unpadded_numbers_are_not_ids(self):
        self.assertEqual(c.mentioned_ids({"title": f"427 00427 1{CID} {CID}9", "body": None}), set())

    def test_missing_and_null_text(self):
        for item in ({}, {"title": None, "body": None}):
            self.assertEqual(c.mentioned_ids(item), set())

    def test_all_matching_items_include_closed_pr_and_issue_body(self):
        items = [{"number": 18, "title": CID, "state": "open"},
                 {"number": 24, "body": CID, "state": "closed"},
                 {"number": 99, "body": f"Certificate {CID}"}, {"number": 7, "title": OTHER_ID}]
        self.assertEqual(c.duplicate_items(items, CID), items[:3])
        self.assertEqual(c.duplicate_items(items, "427"), [])

    def test_file_and_comment_only_mentions_are_indexed(self):
        item = {"title": "No ID here", "files_index": [f"solutions/{CID}/proof/Main.lean"],
                "comments_index": [{"body": f"also studied {OTHER_ID}"}, {"body": None}]}
        self.assertEqual(c.mentioned_ids(item), {CID, OTHER_ID})

    def test_adjacent_text_fields_cannot_merge_two_ids(self):
        item = {"title": "", "body": CID, "files_index": [OTHER_ID]}
        self.assertEqual(c.mentioned_ids(item), {CID, OTHER_ID})

    def test_non_ascii_digits_are_not_official_ids(self):
        self.assertEqual(c.mentioned_ids({"title": "００００００００４２７", "body": "٠٠٠٠٠٠٠٠٤٢٧"}), set())


class PathAndHashTests(FixtureCase):
    def test_valid_path_preserves_leading_zero_id(self):
        actual = c.solution_path(self.root, RELATIVE)
        self.assertEqual(actual, self.path)
        self.assertEqual(actual.parent.name, CID)

    def test_traversal_and_sibling_paths_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        for value in ("../outside", "solutions/../outside", "solutions", str(outside),
                      f"solutions-extra/{CID}/{SUBMISSION}"):
            with self.subTest(value=value), self.assertRaises(c.GateError):
                c.solution_path(self.root, value)

    def test_invalid_id_identity_and_extra_depth_rejected(self):
        for value in (f"solutions/427/{SUBMISSION}", f"solutions/{CID}/someone_else_submission_20260915060000",
                      f"solutions/{CID}/{SUBMISSION}/nested", f"solutions/{CID}/idealistichacker_submission_latest"):
            (self.root / value).mkdir(parents=True, exist_ok=True)
            with self.subTest(value=value), self.assertRaises(c.GateError):
                c.solution_path(self.root, value)

    def test_missing_submission_rejected(self):
        with self.assertRaises(c.GateError):
            c.solution_path(self.root, RELATIVE.replace(CID, OTHER_ID))

    def test_symlink_file_inside_submission_rejected(self):
        target = self.root / "outside.txt"
        target.write_text("private fixture", encoding="utf-8")
        self.symlink(self.path / "linked.txt", target)
        with self.assertRaises(c.GateError):
            c.solution_path(self.root, RELATIVE)

    def test_symlink_directory_escaping_submission_rejected(self):
        target = self.root / "external"
        target.mkdir()
        self.symlink(self.path / "external", target, directory=True)
        with self.assertRaises(c.GateError):
            c.solution_path(self.root, RELATIVE)

    def test_submission_directory_symlink_alias_rejected(self):
        alias = f"solutions/{CID}/idealistichacker_submission_20260915060001"
        self.symlink(self.root / alias, self.path, directory=True)
        with self.assertRaises(c.GateError):
            c.solution_path(self.root, alias)

    def test_hash_binds_content_and_relative_filename(self):
        before = c.content_hash(self.path)
        target = self.write("witness.txt", "certificate A")
        added = c.content_hash(self.path)
        self.assertNotEqual(before, added)
        target.rename(self.path / "renamed-witness.txt")
        self.assertNotEqual(added, c.content_hash(self.path))

    def test_review_record_and_build_cache_do_not_invalidate_hash(self):
        before = c.content_hash(self.path)
        self.write_json("review.json", {"reviewer": "another synthetic reviewer"})
        self.write("lean4/.lake/build/compiled.olean", "generated cache")
        self.write("__pycache__/module.pyc", "generated cache")
        self.assertEqual(before, c.content_hash(self.path))

    def test_nested_data_named_review_json_is_bound_to_review(self):
        # Reproduction input may use this name; only the root attestation needs
        # exclusion to avoid a circular hash dependency.
        self.write_json("data/review.json", {"witness": 1})
        before = c.content_hash(self.path)
        self.write_json("data/review.json", {"witness": 999})
        self.assertNotEqual(before, c.content_hash(self.path))


    def test_text_lf_crlf_preserves_source_hash_content_hash_and_review(self):
        # Write exact bytes so this exercises both checkout styles on every OS.
        self.write(".gitignore", "*.olean\n*.aux\n")
        self.write("evidence.txt", "English evidence\n中文证据\n")
        self.write("data/config.yml", "fixture: true\nvalue: 1\n")
        self.write("data/config.yaml", "fixture: true\nvalue: 2\n")
        self.write_json("data/review.json", {"witness": 1})
        self.write("lean4/lakefile.lean", "import Lake\nopen Lake DSL\npackage fixture\n")
        text_files = [
            "README.md", "main.tex", "reproduce.py", "submission.json",
            "lean4/lean-toolchain", "lean4/lakefile.toml", "lean4/lakefile.lean", "lean4/Main.lean",
            "lean4/Check.lean", ".gitignore", "evidence.txt",
            "data/config.yml", "data/config.yaml", "data/review.json",
        ]
        source_lf = self.source.read_bytes().replace(b"\r\n", b"\n")
        self.source.write_bytes(source_lf)
        expected_source_hash = hashlib.sha256(source_lf).hexdigest()
        self.update_manifest(source_sha256=expected_source_hash)
        for relative in text_files:
            path = self.path / relative
            data = path.read_bytes().replace(b"\r\n", b"\n")
            path.write_bytes(data if data.endswith(b"\n") else data + b"\n")
        self.resign_review()
        original_review = (self.path / "review.json").read_bytes()
        content_lf = c.content_hash(self.path)
        self.assertEqual(c.text_sha(self.source), expected_source_hash)
        self.assertTrue(self.validate()["static"])

        for relative in text_files:
            with self.subTest(text_file=relative):
                path = self.path / relative
                lf = path.read_bytes()
                crlf = lf.replace(b"\n", b"\r\n")
                self.assertNotEqual(lf, crlf)
                path.write_bytes(crlf)
                self.assertEqual(c.content_hash(self.path), content_lf)
        self.source.write_bytes(source_lf.replace(b"\n", b"\r\n"))
        self.assertNotEqual(c.sha(self.source), expected_source_hash)
        self.assertEqual(c.text_sha(self.source), expected_source_hash)
        self.assertEqual((self.path / "review.json").read_bytes(), original_review)
        result = self.validate()
        self.assertEqual(result["content_sha256"], content_lf)
        self.assertFalse(result["executed"])
        self.runner.assert_not_called()

    def test_pdf_and_binary_newlines_remain_byte_sensitive(self):
        lf = b"%PDF-1.7\nsynthetic binary stream\x00\xff\n%%EOF\n"
        crlf = lf.replace(b"\n", b"\r\n")
        for relative in ("main.pdf", "witness.bin"):
            with self.subTest(binary_file=relative):
                path = self.path / relative
                path.write_bytes(lf)
                self.resign_review()
                original_content = c.content_hash(self.path)
                original_raw_sha = c.sha(path)
                path.write_bytes(crlf)
                self.assertEqual(c.sha(path), hashlib.sha256(crlf).hexdigest())
                self.assertNotEqual(c.sha(path), original_raw_sha)
                self.assertNotEqual(c.content_hash(self.path), original_content)
                with self.assertRaisesRegex(c.GateError, "[Rr]eview.*stale"):
                    self.validate()



class StaticValidationTests(FixtureCase):
    def test_complete_static_fixture_never_executes_builds(self):
        result = self.validate()
        self.assertTrue(result["static"])
        self.assertFalse(result["executed"])
        self.assertEqual(result["id"], CID)
        self.runner.assert_not_called()
        saved = c.load(self.root / ".local/validation" / f"{CID}.json")
        self.assertFalse(saved["executed"])

    def test_missing_artifact_rejected_before_build(self):
        (self.path / "main.pdf").unlink()
        with self.assertRaises(c.GateError):
            self.validate(execute=True)
        self.runner.assert_not_called()

    def test_lakefile_lean_is_accepted_as_the_lake_configuration(self):
        (self.path / "lean4/lakefile.toml").unlink()
        self.write("lean4/lakefile.lean", "import Lake\nopen Lake DSL\npackage fixture\n")
        self.resign_review()
        self.assertFalse(self.validate()["executed"])

    def test_changed_source_rejected_even_with_resigned_solution_review(self):
        self.source.write_text("Changed mathematical statement", encoding="utf-8")
        self.resign_review()
        with self.assertRaisesRegex(c.GateError, "[Cc]ontent changed"):
            self.validate()

    def test_source_git_blob_mismatch_rejected(self):
        self.git.side_effect = lambda root, *args: NEW_BLOB
        with self.assertRaisesRegex(c.GateError, "[Bb]lob"):
            self.validate()

    def test_modified_reviewed_artifact_invalidates_review(self):
        self.write("main.tex", "A completely different purported proof")
        with self.assertRaisesRegex(c.GateError, "[Rr]eview.*stale"):
            self.validate()

    def test_manifest_identity_mismatch_rejected(self):
        original = self.manifest.copy()
        for change in ({"id": OTHER_ID}, {"solver": "someone-else"}, {"version": 2}):
            self.manifest = original.copy()
            self.update_manifest(**change)
            with self.subTest(change=change), self.assertRaises(c.GateError):
                self.validate()

    def test_invalid_verdict_rejected(self):
        for verdict in ("ill-posed", "accepted", "", None):
            self.update_manifest(verdict=verdict)
            with self.subTest(verdict=verdict), self.assertRaises(c.GateError):
                self.validate()

    def test_empty_alignment_scope_and_limitations_rejected(self):
        original = self.manifest.copy()
        for field in ("statement_alignment", "formal_scope", "limitations"):
            self.manifest = original.copy()
            self.update_manifest(**{field: "   "})
            with self.subTest(field=field), self.assertRaises(c.GateError):
                self.validate()

    def test_unpinned_toolchain_rejected(self):
        for pin in ("leanprover/lean4:nightly", "leanprover/lean4:latest", "v4.33.1"):
            self.write("lean4/lean-toolchain", pin)
            self.resign_review()
            with self.subTest(pin=pin), self.assertRaises(c.GateError):
                self.validate()

    def test_non_pdf_rejected(self):
        (self.path / "main.pdf").write_bytes(b"not a PDF")
        self.resign_review()
        with self.assertRaises(c.GateError):
            self.validate()

    def test_self_review_rejected(self):
        self.review["reviewer"] = self.manifest["implementation_agent"]
        self.resign_review()
        with self.assertRaises(c.GateError):
            self.validate()

    def test_failed_review_rejected(self):
        self.review["verdict"] = "fail"
        self.resign_review()
        with self.assertRaises(c.GateError):
            self.validate()

    def test_all_review_checks_must_be_literal_true(self):
        for field in self.review["checks"]:
            self.review["checks"][field] = "true"
            self.resign_review()
            with self.subTest(field=field), self.assertRaises(c.GateError):
                self.validate()
            self.review["checks"][field] = True

    def test_missing_author_identity_cannot_establish_independent_review(self):
        self.manifest.pop("implementation_agent")
        self.update_manifest()
        with self.assertRaises(c.GateError):
            self.validate()

    def test_missing_axiom_directive_rejected(self):
        self.write("lean4/Check.lean", "import Main\n")
        self.resign_review()
        with self.assertRaises(c.GateError):
            self.validate()

    def test_undeclared_or_invalid_theorem_names_rejected(self):
        for names in ([], ["bad; injected"], ["bad-name"]):
            self.update_manifest(theorems=names)
            with self.subTest(names=names), self.assertRaises(c.GateError):
                self.validate()


class LeanLexemeTests(OfflineCase):
    def test_prohibited_tokens_rejected(self):
        for token in ("sorry", "admit", "axiom", "native_decide", "unsafe", "implemented_by",
                      "extern", "run_tac", "elab", "macro"):
            with self.subTest(token=token), self.assertRaises(c.GateError):
                c.check_lean_source(f"theorem example : True := by {token}\n")

    def test_conservative_comment_gate_rejects_prohibited_token(self):
        with self.assertRaises(c.GateError):
            c.check_lean_source("-- sorry is intentionally forbidden even in comments\n")

    def test_normal_proof_and_print_axioms_allowed(self):
        c.check_lean_source("theorem demo : True := by trivial\n#print axioms demo\n")

    def test_identifier_substrings_are_not_prohibited_lexemes(self):
        c.check_lean_source("def sorry_count : Nat := 0\ndef external_count : Nat := 1\n")


class ExecutionAndAxiomTests(FixtureCase):
    def test_axiom_free_output_and_identical_pdf_pass_mocked_execution(self):
        result = self.validate(execute=True)
        self.assertTrue(result["executed"])
        self.assertGreaterEqual(self.runner.call_count, 5)
        self.assertIn("axioms", result)
        self.assertEqual((self.path / "main.pdf").read_bytes(), PDF)

    def test_multiline_standard_axiom_footprint_passes(self):
        self.axiom_output = f"'{THEOREM}' depends on axioms: [propext,\n Classical.choice, Quot.sound]"
        self.assertTrue(self.validate(execute=True)["executed"])

    def test_prohibited_axiom_footprints_rejected(self):
        for axiom in ("sorryAx", "Lean.ofReduceBool", "User.unprovedLemma"):
            self.axiom_output = f"'{THEOREM}' depends on axioms: [propext, {axiom}]"
            with self.subTest(axiom=axiom), self.assertRaises(c.GateError):
                self.validate(execute=True)

    def test_missing_wrong_theorem_and_malformed_output_rejected(self):
        for output in ("", "Build completed", "'Submission.other' does not depend on any axioms",
                       f"'{THEOREM}' depends on axioms: [propext"):
            self.axiom_output = output
            with self.subTest(output=output), self.assertRaises(c.GateError):
                self.validate(execute=True)

    def test_conflicting_axiom_reports_rejected(self):
        self.axiom_output = (f"'{THEOREM}' does not depend on any axioms\n"
                             f"'{THEOREM}' depends on axioms: [sorryAx]")
        with self.assertRaises(c.GateError):
            self.validate(execute=True)

    def test_every_advertised_theorem_needs_output(self):
        second = "Submission.second"
        self.write("lean4/Check.lean", f"import Main\n#print axioms {THEOREM}\n#print axioms {second}\n")
        self.update_manifest(theorems=[THEOREM, second])
        with self.assertRaises(c.GateError):
            self.validate(execute=True)

    def test_wrong_installed_version_stops_before_reproduction(self):
        self.lean_version = "Lean (version 4.32.0, Release)"
        with self.assertRaises(c.GateError):
            self.validate(execute=True)
        self.assertEqual(self.runner.call_count, 1)

    def test_prerelease_does_not_satisfy_exact_release_pin(self):
        self.lean_version = f"Lean (version {PIN}-rc1, Release)"
        with self.assertRaises(c.GateError):
            self.validate(execute=True)

    def test_command_failure_stops_without_success_report(self):
        self.runner.side_effect = c.GateError("synthetic failed command")
        with self.assertRaises(c.GateError):
            self.validate(execute=True)
        self.assertEqual(self.runner.call_count, 1)
        self.assertFalse((self.root / ".local/validation" / f"{CID}.json").exists())

    def test_missing_compiled_pdf_rejected(self):
        self.compiled_pdf = None
        with self.assertRaises(c.GateError):
            self.validate(execute=True)

    def test_pdf_mismatch_rejected_without_overwriting_reviewed_pdf(self):
        self.compiled_pdf = b"%PDF-1.7\nchanged compilation\n"
        with self.assertRaises(c.GateError):
            self.validate(execute=True)
        self.assertEqual((self.path / "main.pdf").read_bytes(), PDF)

    def test_build_time_content_change_invalidates_review(self):
        self.mutate_on_reproduce = lambda: self.write("README.md", "Changed after initial review hash check")
        with self.assertRaises(c.GateError):
            self.validate(execute=True)

    def test_main_is_built_before_check_when_not_a_default_lake_target(self):
        # A valid Lake library declaration need not be a default build target.
        # Model that tool behavior, without pretending Lean is installed here.
        self.write("lean4/lakefile.toml", 'name = "fixture"\ndefaultTargets = []\n[[lean_lib]]\nname = "Main"\n')
        self.resign_review()
        compiled = False
        original_run = self.fake_run
        def no_default_target(args, cwd, timeout=300):
            nonlocal compiled
            tail = list(map(str, args))[1:]
            if tail == ["build", "Main"] or ("Main.lean" in tail and "-o" in tail):
                compiled = True
                return "Main compiled explicitly"
            if tail == ["build"]:
                return "No default targets: nothing built"
            if tail == ["env", "lean", "Check.lean"] and not compiled:
                raise c.GateError("unknown module prefix Main: Main.olean not built")
            return original_run(args, cwd, timeout)
        self.runner.side_effect = no_default_target
        try:
            result = self.validate(execute=True)
        except c.GateError as exc:
            self.fail(f"Valid non-default Main target was not explicitly built: {exc}")
        self.assertTrue(result["executed"])


class LockTests(FixtureCase):
    def test_lock_records_owner_and_is_removed_after_success(self):
        lock = self.common / "tlmc-publish.lock"
        with c.publish_lock(self.root):
            record = json.loads(lock.read_text(encoding="utf-8"))
            self.assertEqual(record["pid"], os.getpid())
            self.assertTrue(record["started_at"])
        self.assertFalse(lock.exists())

    def test_existing_lock_cannot_be_deleted_or_overwritten(self):
        lock = self.common / "tlmc-publish.lock"
        lock.write_text("existing-owner", encoding="utf-8")
        with self.assertRaises(c.GateError):
            with c.publish_lock(self.root):
                self.fail("Contender acquired lock")
        self.assertEqual(lock.read_text(encoding="utf-8"), "existing-owner")

    def test_exception_releases_lock(self):
        with self.assertRaisesRegex(RuntimeError, "owner failed"):
            with c.publish_lock(self.root):
                raise RuntimeError("owner failed")
        self.assertFalse((self.common / "tlmc-publish.lock").exists())
        with c.publish_lock(self.root):
            pass

    def test_two_worktrees_share_exclusive_lock(self):
        other = self.root / "another-worktree"
        other.mkdir()
        def contender():
            with c.publish_lock(other):
                return "unexpectedly entered"
        with c.publish_lock(self.root):
            lock = self.common / "tlmc-publish.lock"
            before = lock.read_bytes()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(contender)
                with self.assertRaises(c.GateError):
                    future.result(timeout=10)
            self.assertEqual(lock.read_bytes(), before)


class IdentityTests(OfflineCase):
    def test_correct_identity_with_fork_push_and_no_auto_merge_passes(self):
        api = mock.Mock()
        user = {"login": c.OWNER}
        fork = {"permissions": {"push": True}, "allow_auto_merge": False}
        api.request.side_effect = [user, fork]
        self.assertEqual(c.identity(api), (user, fork))

    def test_wrong_identity_stops_before_fork_lookup(self):
        api = mock.Mock()
        api.request.return_value = {"login": "another-user"}
        with self.assertRaises(c.GateError):
            c.identity(api)
        api.request.assert_called_once_with("/user")

    def test_missing_or_false_push_permission_rejected(self):
        for fork in ({}, {"permissions": {}}, {"permissions": {"admin": True, "push": False}}):
            api = mock.Mock()
            api.request.side_effect = [{"login": c.OWNER}, fork]
            with self.subTest(fork=fork), self.assertRaises(c.GateError):
                c.identity(api)


class ScopeTests(FixtureCase):
    def test_scoped_tracked_dirty_untracked_files_pass(self):
        self.git.side_effect = lambda root, *args: RELATIVE + "/main.tex"
        c.require_clean_scope(self.root, RELATIVE, "upstream/main")

    def test_each_out_of_scope_channel_is_rejected(self):
        for index, name in enumerate(("metadata.csv", f"conjectures/{CID}.md", "credentials.txt")):
            outputs = ["", "", ""]
            outputs[index] = name
            self.git.side_effect = lambda root, *args: (name if (index == 0 and any("...HEAD" in str(x) for x in args)) or (index == 1 and args[-1] == "HEAD") or (index == 2 and args[0] == "ls-files") else "")
            with self.subTest(channel=index), self.assertRaises(c.GateError):
                c.require_clean_scope(self.root, RELATIVE, "upstream/main")

    def test_same_prefix_sibling_is_not_in_scope(self):
        self.git.side_effect = lambda root, *args: RELATIVE + "_extra/main.tex" if args[0] == "diff" else ""
        with self.assertRaises(c.GateError):
            c.require_clean_scope(self.root, RELATIVE, "upstream/main")

    def test_staged_outside_change_hidden_by_worktree_revert_is_rejected(self):
        executable = shutil.which("git")
        if executable is None:
            self.skipTest("Git unavailable for isolated index regression")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k not in {"GH_TOKEN", "GITHUB_TOKEN"}}
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"})
        def local_git(root, *args):
            command = [executable, "-c", "core.hooksPath=" + str(self.root / "disabled-hooks"),
                       "-c", "commit.gpgsign=false", "-c", "user.name=Unit Test",
                       "-c", "user.email=unit-test@example.invalid", *map(str, args)]
            result = REAL_RUN(command, cwd=root, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
            if result.returncode:
                self.fail(f"Isolated Git fixture failed: {args!r}: {result.stderr}")
            return result.stdout.strip()
        local_git(self.root, "init", "--quiet")
        metadata = self.root / "metadata.csv"
        original = "id,proven\n" + CID + ",false\n"
        metadata.write_text(original, encoding="utf-8")
        local_git(self.root, "add", "--", "metadata.csv", RELATIVE, "conjectures")
        local_git(self.root, "commit", "--quiet", "-m", "Synthetic baseline")
        metadata.write_text("id,proven\n" + CID + ",true\n", encoding="utf-8")
        local_git(self.root, "add", "--", "metadata.csv")
        metadata.write_text(original, encoding="utf-8")
        self.assertEqual(local_git(self.root, "diff", "--name-only", "HEAD"), "")
        self.assertEqual(local_git(self.root, "diff", "--cached", "--name-only"), "metadata.csv")
        self.git.side_effect = local_git
        with self.assertRaises(c.GateError):
            c.require_clean_scope(self.root, RELATIVE, "HEAD")


class PublicationTests(FixtureCase):
    def setUp(self):
        super().setUp()
        self.args = argparse.Namespace(submission=RELATIVE, execute=True, lake="mock-lake", tectonic="mock-tectonic", max_open_solution_prs=1)
        self.api = mock.Mock(spec=c.GitHub)
        self.api.request.side_effect = self.fake_request
        self.snapshot = {"items": [], "pulls": [], "fetched_at": c.now(), "upstream": c.UPSTREAM, "deep": True}
        self.refresh = self.patch(c, "refresh", side_effect=lambda root, api, deep=False: self.snapshot)
        self.branch = f"solution/{CID}"
        self.origin = "https://github.com/" + c.FORK
        self.upstream = "https://github.com/" + c.UPSTREAM
        self.fetched_blob = BLOB
        self.git.side_effect = self.fake_git

    def fake_request(self, route, method="GET", payload=None):
        if route == "/user" and method == "GET":
            return {"login": c.OWNER}
        if route == "/repos/" + c.FORK and method == "GET":
            return {"permissions": {"push": True}, "allow_auto_merge": False}
        if route == "/repos/" + c.UPSTREAM + "/pulls" and method == "POST":
            return {"number": 101, "html_url": "https://github.com/example/mock/pull/101"}
        raise AssertionError(f"Unexpected mocked API call: {route!r} {method!r}")

    def fake_git(self, root, *args):
        if args == ("rev-parse", "--git-common-dir"):
            return str(self.common)
        if args == ("remote", "get-url", "origin"):
            return self.origin
        if args == ("remote", "get-url", "upstream"):
            return self.upstream
        if args == ("branch", "--show-current"):
            return self.branch
        if args[0] == "hash-object":
            return BLOB
        if args[0] == "rev-parse":
            return self.fetched_blob if any("upstream/main:" in value for value in args) else BLOB
        if args[0] in {"diff", "ls-files", "fetch", "add", "status", "push", "commit"}:
            return ""
        raise AssertionError(f"Unexpected mocked Git operation: {args!r}")

    def publish(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            c.publish(self.root, self.args, self.api)
        return json.loads(output.getvalue()) if output.getvalue() else None

    def assert_no_git_mutation(self):
        calls = [call.args[1:] for call in self.git.call_args_list if call.args[1] in {"add", "commit", "push"}]
        self.assertEqual(calls, [])

    def assert_no_api_mutation(self):
        calls = [call for call in self.api.request.call_args_list
                 if (call.args[1] if len(call.args) > 1 else call.kwargs.get("method", "GET")) != "GET"]
        self.assertEqual(calls, [])

    def test_no_execute_blocks_before_lock_identity_network_or_git(self):
        self.args.execute = False
        with self.assertRaises(c.GateError):
            self.publish()
        self.api.request.assert_not_called()
        self.refresh.assert_not_called()
        self.git.assert_not_called()
        self.assertFalse((self.common / "tlmc-publish.lock").exists())

    def test_marker_is_idempotent_without_push(self):
        self.snapshot["pulls"] = [{"body": f"<!-- tlmc:{c.OWNER}:{CID} -->", "user": {"login": c.OWNER},
                                   "state": "open", "html_url": "https://github.com/example/mock/pull/1"}]
        self.assertEqual(self.publish()["state"], "already_submitted")
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_duplicate_issue_blocks_before_build_and_mutation(self):
        self.snapshot["items"] = [{"number": 18, "title": f"Disproof {CID}"}]
        with self.assertRaises(c.GateError):
            self.publish()
        self.runner.assert_not_called()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_duplicate_only_in_newer_pull_snapshot_also_blocks(self):
        self.snapshot["pulls"] = [{"number": 24, "title": CID, "state": "open", "user": {"login": "another-author"}}]
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_active_own_pr_enforces_wip_limit(self):
        self.snapshot["pulls"] = [{"body": "another task", "state": "open", "user": {"login": c.OWNER}}]
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_documented_two_pr_exception_allows_exactly_one_existing_pr(self):
        self.args.max_open_solution_prs = 2
        self.snapshot["pulls"] = [{"body": "another task", "state": "open", "user": {"login": c.OWNER}}]
        self.assertEqual(self.publish()["state"], "awaiting_upstream_review")

    def test_two_pr_exception_still_blocks_two_existing_prs(self):
        self.args.max_open_solution_prs = 2
        self.snapshot["pulls"] = [
            {"body": "task one", "state": "open", "user": {"login": c.OWNER}},
            {"body": "task two", "state": "open", "user": {"login": c.OWNER}},
        ]
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_invalid_wip_limit_blocks_before_mutation(self):
        self.args.max_open_solution_prs = 3
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_wrong_remote_rejected(self):
        self.origin = "https://github.com/another/repo"
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_wrong_branch_rejected(self):
        self.branch = "main"
        with self.assertRaises(c.GateError):
            self.publish()
        self.runner.assert_not_called()
        self.assert_no_git_mutation()

    def test_validation_failure_prevents_stage_push_and_post(self):
        self.runner.side_effect = c.GateError("Synthetic Lean failure")
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()
        self.assertFalse((self.common / "tlmc-publish.lock").exists())

    def test_latest_upstream_source_change_blocks_before_mutation(self):
        self.fetched_blob = NEW_BLOB
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_git_mutation()
        self.assert_no_api_mutation()

    def test_mocked_success_pushes_fork_nonforce_and_requests_review(self):
        self.assertEqual(self.publish()["state"], "awaiting_upstream_review")
        pushes = [call.args[1:] for call in self.git.call_args_list if call.args[1] == "push"]
        self.assertEqual(pushes, [("push", "-u", "origin", f"solution/{CID}")])
        posts = [call for call in self.api.request.call_args_list if len(call.args) > 1 and call.args[1] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].args[2]["head"], f"{c.OWNER}:solution/{CID}")
        self.assertEqual(posts[0].args[2]["base"], "main")
        self.assertEqual(self.refresh.call_count, 2)
        self.assertTrue(all(call.kwargs.get("deep") for call in self.refresh.call_args_list))
        self.urlopen.assert_not_called()
        self.process.assert_not_called()

    def test_duplicate_after_push_prevents_post(self):
        self.refresh.side_effect = [self.snapshot, {**self.snapshot, "items": [{"number": 24, "title": CID}]}]
        with self.assertRaises(c.GateError):
            self.publish()
        self.assert_no_api_mutation()

    def test_post_timeout_is_not_blindly_retried(self):
        real_fake_request = self.fake_request
        def timeout_on_post(route, method="GET", payload=None):
            if method == "POST":
                raise TimeoutError("Synthetic lost response after mutation")
            return real_fake_request(route, method, payload)
        self.api.request.side_effect = timeout_on_post
        with self.assertRaises((TimeoutError, c.GateError)):
            self.publish()
        with self.assertRaises(c.GateError):
            self.publish()
        posts = [call for call in self.api.request.call_args_list if len(call.args) > 1 and call.args[1] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertFalse((self.common / "tlmc-publish.lock").exists())


class CliTests(FixtureCase):
    def test_no_execute_blocks_publish_without_api_access(self):
        self.credentials.side_effect = None
        self.credentials.return_value = "synthetic-token"
        api = mock.Mock()
        self.patch(c, "GitHub", return_value=api)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = c.main(["--repo", str(self.root), "publish", RELATIVE])
        self.assertEqual(code, 2)
        self.assertIn("--execute", stderr.getvalue())
        api.request.assert_not_called()
        self.runner.assert_not_called()

    def test_no_execute_should_not_even_read_credentials(self):
        self.credentials.side_effect = None
        self.credentials.return_value = "synthetic-token"
        api_type = self.patch(c, "GitHub")
        with contextlib.redirect_stderr(io.StringIO()):
            code = c.main(["--repo", str(self.root), "publish", RELATIVE])
        self.assertEqual(code, 2)
        self.credentials.assert_not_called()
        api_type.assert_not_called()

    def test_issue_without_execute_blocks_before_reading_draft_or_identity(self):
        args = argparse.Namespace(execute=False, draft=str(self.root / "nonexistent.json"))
        api = mock.Mock()
        with self.assertRaises(c.GateError):
            c.create_issue(self.root, args, api)
        api.request.assert_not_called()
        self.git.assert_not_called()

    def test_static_validate_cli_does_not_fetch_credentials_or_execute(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = c.main(["--repo", str(self.root), "validate", RELATIVE, "--static-only"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(output.getvalue())["executed"])
        self.credentials.assert_not_called()
        self.runner.assert_not_called()


class DeepRefreshTests(FixtureCase):
    def setUp(self):
        super().setUp()
        self.base_route = "/repos/" + c.UPSTREAM
        self.pull = {"number": 12, "title": "No identifier in title", "body": "",
                     "head": {"sha": BLOB}, "base": {"sha": "c" * 40},
                     "state": "open", "user": {"login": "another-author"}}
        self.item = {"number": 12, "title": "No identifier here either", "body": None, "comments": 1}
        self.files = [{"filename": f"solutions/{CID}/submission/Main.lean"}]
        self.comments = [{"body": f"Related work {OTHER_ID}"}]
        self.api = mock.Mock(spec=c.GitHub)
        self.api.pages.side_effect = self.pages

    def pages(self, route):
        data = {
            self.base_route + "/issues?state=all": [self.item],
            self.base_route + "/pulls?state=all": [self.pull],
            self.base_route + "/pulls/12/files": self.files,
            self.base_route + "/issues/12/comments": self.comments,
        }
        if route not in data:
            raise AssertionError(f"Unexpected mocked endpoint: {route}")
        if isinstance(data[route], Exception):
            raise data[route]
        return json.loads(json.dumps(data[route]))

    def endpoint_calls(self, suffix):
        return sum(call.args == (self.base_route + suffix,) for call in self.api.pages.call_args_list)

    def test_shallow_refresh_never_loads_enrichment_endpoints(self):
        snapshot = c.refresh(self.root, self.api)
        self.assertFalse(snapshot["deep"])
        self.assertEqual(self.api.pages.call_count, 2)
        self.assertEqual(self.endpoint_calls("/pulls/12/files"), 0)

    def test_deep_snapshot_indexes_files_and_comments_and_is_saved(self):
        snapshot = c.refresh(self.root, self.api, deep=True)
        self.assertTrue(snapshot["deep"])
        self.assertIn(CID, c.mentioned_ids(snapshot["pulls"][0]))
        self.assertIn(OTHER_ID, c.mentioned_ids(snapshot["items"][0]))
        self.assertEqual(c.load(self.root / ".local/audit/github-deep.json"), snapshot)
        self.assertEqual(c.load(self.root / ".local/audit/github.json"), snapshot)

    def test_unchanged_head_and_base_reuse_files_but_refresh_comments(self):
        c.refresh(self.root, self.api, deep=True)
        self.comments = [{"body": "Updated discussion mentions 00000000116"}]
        snapshot = c.refresh(self.root, self.api, deep=True)
        self.assertEqual(self.endpoint_calls("/pulls/12/files"), 1)
        self.assertEqual(self.endpoint_calls("/issues/12/comments"), 2)
        self.assertIn("00000000116", c.mentioned_ids(snapshot["items"][0]))
        self.assertNotIn(OTHER_ID, c.mentioned_ids(snapshot["items"][0]))

    def test_head_change_invalidates_file_cache(self):
        c.refresh(self.root, self.api, deep=True)
        self.pull["head"]["sha"] = NEW_BLOB
        self.files = [{"filename": f"solutions/{OTHER_ID}/submission/Main.lean"}]
        snapshot = c.refresh(self.root, self.api, deep=True)
        self.assertEqual(self.endpoint_calls("/pulls/12/files"), 2)
        self.assertIn(OTHER_ID, c.mentioned_ids(snapshot["pulls"][0]))
        self.assertNotIn(CID, c.mentioned_ids(snapshot["pulls"][0]))

    def test_base_change_also_invalidates_file_cache(self):
        # The PR diff depends on its base as well as its unchanged head.
        c.refresh(self.root, self.api, deep=True)
        self.pull["base"]["sha"] = "d" * 40
        self.files = [{"filename": f"solutions/{OTHER_ID}/submission/Main.lean"}]
        snapshot = c.refresh(self.root, self.api, deep=True)
        self.assertEqual(self.endpoint_calls("/pulls/12/files"), 2)
        self.assertIn(OTHER_ID, c.mentioned_ids(snapshot["pulls"][0]))

    def test_file_limit_fails_closed_and_preserves_last_good_snapshot(self):
        c.refresh(self.root, self.api, deep=True)
        cache = self.root / ".local/audit/github-deep.json"
        before = cache.read_bytes()
        self.pull["head"]["sha"] = NEW_BLOB
        self.files = [{"filename": f"file-{i}.txt"} for i in range(3000)]
        with self.assertRaises(c.GateError):
            c.refresh(self.root, self.api, deep=True)
        self.assertEqual(cache.read_bytes(), before)

    def test_enrichment_failure_does_not_publish_partial_cache(self):
        c.refresh(self.root, self.api, deep=True)
        paths = [self.root / ".local/audit/github-deep.json", self.root / ".local/audit/github.json"]
        before = [path.read_bytes() for path in paths]
        self.comments = c.GateError("Synthetic comment endpoint failure")
        with self.assertRaises(c.GateError):
            c.refresh(self.root, self.api, deep=True)
        self.assertEqual([path.read_bytes() for path in paths], before)


class IssuePublicationTests(FixtureCase):
    def setUp(self):
        super().setUp()
        self.draft = {"key": "clarify-test-contract", "title": "Clarify the synthetic submission contract",
                      "body": "Synthetic substantive issue draft for offline regression testing. " * 4,
                      "reviewed": True}
        self.draft_path = self.root / "draft.json"
        self.save_draft()
        self.args = argparse.Namespace(execute=True, draft=str(self.draft_path))
        self.items = []
        self.api = mock.Mock(spec=c.GitHub)
        self.api.pages.side_effect = lambda route: self.items
        self.api.request.side_effect = self.request

    def save_draft(self):
        self.draft_path.write_text(json.dumps(self.draft), encoding="utf-8")

    def request(self, route, method="GET", payload=None):
        if route == "/user" and method == "GET":
            return {"login": c.OWNER}
        if route == "/repos/" + c.FORK and method == "GET":
            return {"permissions": {"push": True}}
        if route == "/repos/" + c.UPSTREAM + "/issues" and method == "POST":
            return {"number": 102, "html_url": "https://github.com/example/mock/issues/102"}
        raise AssertionError(f"Unexpected mocked issue request: {route} {method}")

    def issue(self, root=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            c.create_issue(root or self.root, self.args, self.api)
        return json.loads(output.getvalue()) if output.getvalue() else None

    def posts(self):
        return [call for call in self.api.request.call_args_list if len(call.args) > 1 and call.args[1] == "POST"]

    def item(self, days_ago=1, **extra):
        value = {"number": 100, "title": "An unrelated existing issue", "body": "unrelated",
                 "user": {"login": c.OWNER}, "html_url": "https://github.com/example/mock/issues/100",
                 "created_at": (c.dt.datetime.now(c.dt.timezone.utc) - c.dt.timedelta(days=days_ago)).isoformat()}
        value.update(extra)
        return value

    def test_invalid_key_cannot_traverse_ledger_path(self):
        self.draft["key"] = "../../outside"
        self.save_draft()
        with self.assertRaises(c.GateError):
            self.issue()
        self.api.request.assert_not_called()
        self.assertFalse((self.common / "tlmc-publish.lock").exists())

    def test_unreviewed_or_insubstantial_drafts_block_before_identity(self):
        original = self.draft.copy()
        for change in ({"reviewed": False}, {"reviewed": "true"}, {"title": "tiny"}, {"body": "tiny"}):
            self.draft = {**original, **change}
            self.save_draft()
            with self.subTest(change=change), self.assertRaises(c.GateError):
                self.issue()
        self.api.request.assert_not_called()

    def test_existing_marker_is_idempotent_even_with_different_title(self):
        self.items = [self.item(body=f"<!-- tlmc-issue:{c.OWNER}:{self.draft['key']} -->")]
        self.assertEqual(self.issue()["state"], "already_exists")
        self.assertEqual(self.posts(), [])

    def test_case_insensitive_existing_title_is_idempotent(self):
        self.items = [self.item(title=self.draft["title"].upper())]
        self.assertEqual(self.issue()["state"], "already_exists")
        self.assertEqual(self.posts(), [])

    def test_recent_own_standalone_issue_enforces_weekly_limit(self):
        self.items = [self.item(days_ago=1)]
        with self.assertRaises(c.GateError):
            self.issue()
        self.assertEqual(self.posts(), [])

    def test_old_issue_other_authors_and_prs_do_not_consume_weekly_allowance(self):
        self.items = [self.item(days_ago=8), self.item(user={"login": "another-author"}),
                      self.item(pull_request={"url": "https://api.github.com/example/mock/pulls/1"})]
        self.assertEqual(self.issue()["state"], "created")
        self.assertEqual(len(self.posts()), 1)
        self.assertIn(f"<!-- tlmc-issue:{c.OWNER}:{self.draft['key']} -->", self.posts()[0].args[2]["body"])
        self.urlopen.assert_not_called()
        self.process.assert_not_called()

    def test_unresolved_post_timeout_never_blindly_reposts(self):
        original = self.request
        def timeout(route, method="GET", payload=None):
            if method == "POST":
                raise TimeoutError("Synthetic lost response")
            return original(route, method, payload)
        self.api.request.side_effect = timeout
        with self.assertRaises(TimeoutError):
            self.issue()
        with self.assertRaises(c.GateError):
            self.issue()
        self.assertEqual(len(self.posts()), 1)
        self.assertFalse((self.common / "tlmc-publish.lock").exists())

    def test_remote_marker_reconciles_timed_out_attempt_without_repost(self):
        original = self.request
        def timeout(route, method="GET", payload=None):
            if method == "POST":
                raise TimeoutError("Synthetic lost response")
            return original(route, method, payload)
        self.api.request.side_effect = timeout
        with self.assertRaises(TimeoutError):
            self.issue()
        self.items = [self.item(body=f"<!-- tlmc-issue:{c.OWNER}:{self.draft['key']} -->")]
        self.assertEqual(self.issue()["state"], "already_exists")
        self.assertEqual(len(self.posts()), 1)

    def test_unresolved_attempt_must_block_other_worktree_too(self):
        original = self.request
        def timeout(route, method="GET", payload=None):
            if method == "POST":
                raise TimeoutError("Synthetic lost response")
            return original(route, method, payload)
        self.api.request.side_effect = timeout
        with self.assertRaises(TimeoutError):
            self.issue()
        other = self.root / "another-worktree"
        other.mkdir()
        try:
            self.issue(root=other)
        except (TimeoutError, c.GateError):
            pass
        self.assertEqual(len(self.posts()), 1, "Unresolved mutation was retried from a second worktree")


if __name__ == "__main__":
    unittest.main()
