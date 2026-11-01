import asyncio
import io
import json
import sqlite3
import stat
import struct
import sys
import tempfile
import threading
import unittest
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "discord_bot/src"), str(ROOT / "discord_bot/external/s2protocol")]
from aok_bot import bot, replay_inputs as inputs, replay_worker as worker
from aok_bot.models import PlayerStats, ReplaySummary
from aok_bot.protocols import COMPATIBLE_PROTOCOLS
from aok_bot.reporting import markdown_report, save_markdown_report
from aok_bot.storage import Storage


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.archive = self.root / "input.zip"
        self.limits = inputs.ReplayLimits(upload_bytes=4096, replay_bytes=64,
            expanded_bytes=100, zip_entries=5, replay_members=3, ratio=10)

    def zip(self, entries, compression=zipfile.ZIP_STORED):
        with zipfile.ZipFile(self.archive, "w", compression=compression) as archive:
            for name, data in entries:
                archive.writestr(name, data)
        return self.archive

    def extract(self, limits=None):
        return inputs.extract_replay_paths(self.archive, self.cache, limits or self.limits)

    def test_paths_links_encryption_and_compression_preflight(self):
        for name in ("../x.SC2Replay", "a/../x.SC2Replay", "/x.SC2Replay",
                     "C:/x.SC2Replay", "C:x.SC2Replay", "..\\x.SC2Replay", "\\x.SC2Replay"):
            with self.subTest(name=name):
                self.zip([(name, b"x")])
                with self.assertRaises(inputs.ReplayInputError):
                    self.extract()
                self.assertFalse(self.cache.exists())
        link = zipfile.ZipInfo("x.SC2Replay")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.zip([(link, b"target")])
        with self.assertRaises(inputs.ReplayInputError):
            self.extract()
        self.zip([("x.SC2Replay", b"x")], zipfile.ZIP_BZIP2)
        with self.assertRaises(inputs.ReplayInputError):
            self.extract()
        self.zip([("x.SC2Replay", b"x")])
        raw = bytearray(self.archive.read_bytes())
        for marker, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            index = raw.index(marker) + offset
            struct.pack_into("<H", raw, index, struct.unpack_from("<H", raw, index)[0] | 1)
        self.archive.write_bytes(raw)
        with self.assertRaises(inputs.ReplayInputError):
            self.extract()
        self.assertFalse(self.cache.exists())

    def test_declared_counts_sizes_ratio_and_empty(self):
        cases = [([("x.SC2Replay", b"")], self.limits),
                 ([("x.SC2Replay", b"x" * 65)], self.limits),
                 ([(f"{i}.txt", b"x") for i in range(6)], self.limits),
                 ([(f"{i}.SC2Replay", b"x") for i in range(4)], self.limits),
                 ([("a.SC2Replay", b"a" * 60), ("b.SC2Replay", b"b" * 60)], self.limits)]
        for entries, limits in cases:
            self.zip(entries)
            with self.assertRaises(inputs.ReplayInputError):
                self.extract(limits)
            self.assertFalse(self.cache.exists())
        self.zip([("x.SC2Replay", b"x" * 60)], zipfile.ZIP_DEFLATED)
        with self.assertRaises(inputs.ReplayInputError):
            self.extract(replace(self.limits, ratio=1))
        self.archive.write_bytes(b"")
        with self.assertRaises(inputs.ReplayInputError):
            self.extract()

    def test_stream_actual_limit_and_crc_cleanup(self):
        self.zip([("x.SC2Replay", b"unique_payload")])
        with patch.object(zipfile.ZipFile, "open", return_value=io.BytesIO(b"x" * 65)):
            with self.assertRaises(inputs.ReplayInputError):
                self.extract()
        self.assertEqual(list(self.cache.iterdir()), [])
        raw = self.archive.read_bytes().replace(b"unique_payload", b"broken_payload")
        self.archive.write_bytes(raw)
        with self.assertRaises(inputs.ReplayInputError):
            self.extract()
        self.assertEqual(list(self.cache.iterdir()), [])
        self.assertTrue(self.archive.exists())
        self.zip([("a.SC2Replay", b"a" * 60), ("b.SC2Replay", b"b")])
        with patch.object(zipfile.ZipFile, "open", side_effect=[io.BytesIO(b"a" * 60), io.BytesIO(b"b" * 60)]):
            with self.assertRaises(inputs.ReplayInputError):
                self.extract()
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_uppercase_duplicates_ignore_nonreplays_concurrent_and_poison(self):
        self.zip([("same.SC2REPLAY", b"a"), ("same.SC2REPLAY", b"b"),
                  ("other.sc2replay", b"a"), ("ignored.txt", b"ignored_payload")])
        self.archive.write_bytes(self.archive.read_bytes().replace(b"ignored_payload", b"corrupt_payload"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.extract(), range(8)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(len(results[0]), 2)
        self.assertEqual({p.read_bytes() for p in results[0]}, {b"a", b"b"})
        self.assertEqual(len(list(self.cache.iterdir())), 2)
        poison = results[0][0]
        poison.write_bytes(b"z")
        with self.assertRaises(inputs.ReplayInputError):
            self.extract()
        self.assertEqual(poison.read_bytes(), b"z")
        self.assertEqual(len(list(self.cache.iterdir())), 2)

    def test_raw_stream_hash_and_caps(self):
        path = self.root / "X.SC2REPLAY"
        path.write_bytes(b"abc")
        result = inputs.extract_replay_paths(path, self.cache, self.limits)[0]
        self.assertEqual(result.name, inputs.stable_copy_name(path))
        self.assertEqual(len(result.stem), 64)
        for limits in (replace(self.limits, upload_bytes=2), replace(self.limits, replay_bytes=2)):
            with self.assertRaises(inputs.ReplayInputError):
                inputs.extract_replay_paths(path, self.cache, limits)


class PersistenceTests(unittest.TestCase):
    def test_closed_connections_rollback_and_concurrent_good_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            initialization = []
            connect = sqlite3.connect
            def initial_connect(*args, **kwargs):
                connection = connect(*args, **kwargs)
                initialization.append(connection)
                return connection
            with patch("sqlite3.connect", side_effect=initial_connect):
                storage = Storage(Path(directory) / "db.sqlite")
            for connection in initialization:
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")
            opened, original = [], storage.connect
            def observe():
                connection = original()
                opened.append(connection)
                return connection
            summary = ReplaySummary(Path("x"), parser_ok=True, players=[PlayerStats("Ada", kills=5)])
            with patch.object(storage, "connect", side_effect=observe):
                first = storage.save_replay(summary)
                broken = replace(summary, players=[PlayerStats(None)])
                with self.assertRaises(sqlite3.IntegrityError):
                    storage.save_replay(broken)
                self.assertEqual(storage.player_profile("Ada")["kills"], 5)
                storage.leaderboard()
                bad = replace(summary, parser_ok=False, players=[])
                self.assertEqual(storage.save_replay(bad), first)
            for connection in opened:
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(storage.save_replay, [bad, summary] * 8))
            self.assertEqual(storage.player_profile("Ada")["games"], 1)
            self.assertEqual(storage.player_profile("Ada")["kills"], 5)

    def test_report_invalid_mode_and_unique_modes_reruns(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "reports"
            summary = ReplaySummary(Path("a" * 300 + ".SC2Replay"))
            with self.assertRaises(ValueError):
                save_markdown_report(summary, target, "../../bad")
            self.assertFalse(target.exists())
            paths = [save_markdown_report(summary, target, m) for m in ("stats", "stats", "team", "coaching")]
            self.assertEqual(len(set(paths)), 4)
            self.assertTrue(all(len(p.name) < 120 and p.read_text() for p in paths))


class WorkerTests(unittest.TestCase):
    def test_timeout_crash_overflow_and_malformed(self):
        for script, message in (("import time; time.sleep(3)", "timed out"),
                                ("raise SystemExit(2)", "failed"),
                                ("print('x'*10000)", "output limit")):
            with self.subTest(script=script), self.assertRaisesRegex(worker.ReplayWorkerError, message):
                worker._run([sys.executable, "-I", "-c", script], deadline=.15 if "sleep" in script else 3, output_bytes=100)
        for data in (b"garbage", b"{}", b'{"version":1,"summary":{}}'):
            with self.assertRaises(worker.ReplayWorkerError):
                worker.decode_summary(data)
        value = json.loads(worker.encode_summary(ReplaySummary(Path("x"))))
        value["summary"]["parser_ok"] = "true"
        with self.assertRaises(worker.ReplayWorkerError):
            worker.decode_summary(json.dumps(value).encode())
        fabricated = ReplaySummary(Path("x"), parser_ok=True)
        with self.assertRaises(worker.ReplayWorkerError):
            worker.decode_summary(worker.encode_summary(fabricated))

    def test_counter_roundtrip_and_secret_free_child(self):
        summary = ReplaySummary(Path("x"), players=[PlayerStats("A", unit_type_counts=Counter(Knight=2))])
        decoded = worker.decode_summary(worker.encode_summary(summary))
        self.assertIsInstance(decoded.players[0].unit_type_counts, Counter)
        self.assertEqual(summary.to_dict(), decoded.to_dict())
        with patch.dict("os.environ", {"DISCORD_TOKEN": "secret", "PYTHONPATH": "secret", "HTTPS_PROXY": "secret"}):
            data = worker._run([sys.executable, "-I", "-c", "import os,json; print(json.dumps(dict(os.environ)))"], deadline=3, output_bytes=10000)
        environment = json.loads(data)
        self.assertFalse({"DISCORD_TOKEN", "PYTHONPATH", "HTTPS_PROXY"} & environment.keys())

    def test_real_native_and_mapped_subprocess_roundtrip(self):
        audit = ROOT / "analysis_outputs/refactored_full/replay_audit_records.jsonl"
        if not audit.exists():
            self.skipTest("Local corpus unavailable")
        rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
        from aok_bot.replay_parser import parse_replay
        for mapped in (False, True):
            candidates = [r for r in rows if r["parse_ok"] and Path(r["path"]).exists()
                          and (int(r["metadata"]["build"]) in COMPATIBLE_PROTOCOLS) == mapped
                          and r["metadata"].get("duration_seconds", 0) >= 60]
            if not candidates:
                self.skipTest("Representative native/mapped local corpus unavailable")
            row = min(candidates, key=lambda r: r["size_bytes"])
            path = Path(row["path"])
            with self.subTest(mapped=mapped):
                trusted = parse_replay(path)
                isolated = worker.parse_replay_isolated(path)
                self.assertTrue(isolated.parser_ok)
                self.assertEqual(isolated.to_dict(), trusted.to_dict())
                self.assertEqual(markdown_report(isolated), markdown_report(trusted))
                self.assertEqual(worker.decode_summary(worker.encode_summary(trusted)).to_dict(), trusted.to_dict())


class BotTests(unittest.IsolatedAsyncioTestCase):
    def interaction(self):
        return SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
                               followup=SimpleNamespace(send=AsyncMock()))

    async def test_busy_cancelled_interaction_keeps_ownership(self):
        admission = bot.JobAdmission(1)
        entered, release = asyncio.Event(), asyncio.Event()
        async def job():
            entered.set()
            await release.wait()
        task = admission.submit(job)
        await entered.wait()
        async def waiter():
            await asyncio.shield(task)
        waiter_task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        waiter_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter_task
        self.assertIsNone(admission.submit(job))
        self.assertFalse(task.done())
        interaction = self.interaction()
        with patch.object(bot, "admission", admission):
            await bot.aok_analyze.callback(interaction, SimpleNamespace(filename="x.zip"))
        self.assertIn("busy", interaction.response.send_message.call_args.args[0])
        release.set()
        await task
        await asyncio.sleep(0)
        self.assertEqual(len(admission.jobs), 0)

    async def test_owned_thread_finishes_before_cancellation_cleanup(self):
        started, release = threading.Event(), threading.Event()
        def function():
            started.set()
            release.wait(2)
        task = asyncio.create_task(bot.owned_thread(function))
        await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_invalid_mode_no_disk_or_database(self):
        with patch.object(bot, "settings", None), patch.object(bot, "storage", None):
            interaction = self.interaction()
            await bot.aok_analyze.callback(interaction, SimpleNamespace(filename="x.zip"), "bad")
            interaction.response.send_message.assert_awaited_once()
            interaction.response.defer.assert_not_awaited()

    async def test_cancelled_handler_keeps_upload_until_extraction_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.zip"
            path.write_bytes(b"owned")
            started, release = threading.Event(), threading.Event()
            def extract(*args):
                started.set()
                release.wait(3)
                self.assertTrue(path.exists())
                return []
            settings = SimpleNamespace(replays_dir=Path(directory), input_limits=inputs.DEFAULT_LIMITS)
            admission = bot.JobAdmission(1)
            with patch.object(bot, "settings", settings), patch.object(bot, "admission", admission), \
                 patch.object(bot, "save_attachment", AsyncMock(return_value=path)), \
                 patch.object(bot, "extract_replay_paths", side_effect=extract):
                handler = asyncio.create_task(bot.aok_analyze.callback(self.interaction(), SimpleNamespace(filename="x.zip")))
                await asyncio.to_thread(started.wait, 2)
                handler.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await handler
                self.assertEqual(len(admission.jobs), 1)
                self.assertTrue(path.exists())
                job = next(iter(admission.jobs))
                release.set()
                await job
                await asyncio.sleep(0)
                self.assertFalse(path.exists())
                self.assertFalse(admission.jobs)

    async def test_download_caps_unique_paths_cleanup_and_timeout(self):
        class Response:
            content_length = None
            def raise_for_status(self): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            @property
            def content(self): return self
            async def iter_chunked(self, n):
                for chunk in self.chunks:
                    if isinstance(chunk, BaseException):
                        raise chunk
                    yield chunk
        response = Response()
        session = SimpleNamespace(get=lambda url: response)
        class Session:
            async def __aenter__(self): return session
            async def __aexit__(self, *args): pass
        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(uploads_dir=Path(directory), download_timeout=7,
                                       input_limits=inputs.ReplayLimits(upload_bytes=4))
            attachment = SimpleNamespace(filename="../../same.SC2Replay", size=3, url="https://invalid.test/?secret")
            with patch.object(bot, "settings", settings), patch.object(bot.aiohttp, "ClientSession", return_value=Session()) as factory:
                response.chunks = [b"ab", b"c"]
                a, b = await bot.save_attachment(attachment), await bot.save_attachment(attachment)
                self.assertNotEqual(a, b)
                self.assertEqual(a.read_bytes(), b"abc")
                self.assertEqual(factory.call_args.kwargs["timeout"].total, 7)
                for chunks in ([b"abc", b"de"], [], [b"x"], [asyncio.TimeoutError()]):
                    response.chunks = chunks
                    with self.assertRaises((ValueError, asyncio.TimeoutError)):
                        await bot.save_attachment(attachment)
                response.content_length = 5
                with self.assertRaises(ValueError):
                    await bot.save_attachment(attachment)
                attachment.size = 5
                with self.assertRaises(ValueError):
                    await bot.save_attachment(attachment)
                self.assertEqual(set(Path(directory).iterdir()), {a, b})

    async def test_report_failure_never_persists_and_replays_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            upload = Path(directory) / "upload.zip"
            upload.write_bytes(b"x")
            settings = SimpleNamespace(replays_dir=Path(directory), reports_dir=Path(directory), input_limits=inputs.DEFAULT_LIMITS)
            history = SimpleNamespace(save_replay=unittest.mock.Mock())
            summary = ReplaySummary(Path("x"), warnings=["Replay parse failed: private/path?token=secret"])
            report = Path(directory) / "report.md"
            report.write_text("report")
            async def thread(function, *args):
                return [Path("a"), Path("b")] if function is inputs.extract_replay_paths else summary
            with patch.object(bot, "settings", settings), patch.object(bot, "storage", history), \
                 patch.object(bot, "save_attachment", AsyncMock(return_value=upload)), \
                 patch.object(bot, "owned_thread", side_effect=thread), \
                 patch.object(bot, "save_markdown_report", side_effect=[OSError("private"), report]) as render:
                interaction = self.interaction()
                await bot._analyze_job(interaction, None, "stats")
                history.save_replay.assert_called_once_with(summary)
                message = interaction.followup.send.call_args.args[0]
                self.assertIn("1 failed", message)
                self.assertNotIn("private", message)
                self.assertNotIn("private", str(render.call_args.args[0].warnings))
                self.assertFalse(upload.exists())
            upload.write_bytes(b"new request")
            history.save_replay.side_effect = sqlite3.OperationalError("private database path")
            with patch.object(bot, "settings", settings), patch.object(bot, "storage", history), \
                 patch.object(bot, "save_attachment", AsyncMock(return_value=upload)), \
                 patch.object(bot, "owned_thread", side_effect=thread), \
                 patch.object(bot, "save_markdown_report", return_value=report):
                interaction = self.interaction()
                await bot._analyze_job(interaction, None, "stats")
                message = interaction.followup.send.call_args.args[0]
                self.assertIn("2 report(s) could not be saved to history", message)
                self.assertNotIn("private", message)
                self.assertFalse(upload.exists())


class ResidualLimitTests(unittest.TestCase):
    def test_directory_limit_precedes_zipfile_even_with_forged_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path, cache = Path(directory) / "many.zip", Path(directory) / "cache"
            with zipfile.ZipFile(path, "w") as archive:
                for index in range(20000):
                    archive.writestr(f"{index}/", b"")
            raw = bytearray(path.read_bytes())
            for forged in (False, True):
                if forged:
                    struct.pack_into("<2H", raw, raw.rfind(b"PK\x05\x06") + 8, 1, 1)
                    path.write_bytes(raw)
                with self.subTest(forged=forged), patch.object(inputs.zipfile, "ZipFile") as factory:
                    with self.assertRaisesRegex(inputs.ReplayInputError, "Too many ZIP entries"):
                        inputs.extract_replay_paths(path, cache)
                    factory.assert_not_called()
                self.assertFalse(cache.exists())

    def test_directory_malformed_ranges_spans_truncation_and_zip64(self):
        with tempfile.TemporaryDirectory() as directory:
            path, cache = Path(directory) / "bad.zip", Path(directory) / "cache"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("a.SC2Replay", b"a")
            raw = path.read_bytes()
            end, central = raw.rfind(b"PK\x05\x06"), raw.index(b"PK\x01\x02")
            cases = [raw[:-1], raw[:central + 20] + raw[end:]]
            for offset, fmt, value in ((end + 16, "<I", len(raw)),
                                       (end + 4, "<H", 1), (end + 10, "<H", 0),
                                       (end + 12, "<I", 0xffffffff),
                                       (central + 28, "<H", 65535),
                                       (central + 34, "<H", 1),
                                       (central + 42, "<I", 0xffffffff)):
                changed = bytearray(raw)
                struct.pack_into(fmt, changed, offset, value)
                cases.append(changed)
            cases.append(raw[:end] + b"PK\x06\x07" + bytes(16) + raw[end:])
            for index, data in enumerate(cases):
                path.write_bytes(data)
                with self.subTest(case=index), patch.object(inputs.zipfile, "ZipFile") as factory:
                    with self.assertRaises(inputs.ReplayInputError):
                        inputs.extract_replay_paths(path, cache)
                    factory.assert_not_called()
            self.assertFalse(cache.exists())

    def test_commented_zip_with_directories_and_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path, cache = Path(directory) / "valid.zip", Path(directory) / "cache"
            with zipfile.ZipFile(path, "w") as archive:
                archive.comment = b"ordinary archive comment" * 2000
                archive.writestr("folder/", b"")
                archive.writestr("folder/a.SC2Replay", b"replay")
            path.write_bytes(b"self extracting prefix" + path.read_bytes())
            result = inputs.extract_replay_paths(path, cache)
            self.assertEqual([p.read_bytes() for p in result], [b"replay"])

    def test_invalid_download_timeouts_rejected_without_io(self):
        from aok_bot.config import Settings
        values = (float("nan"), float("inf"), -float("inf"), True, False, None, "1", 0, -1)
        args = ("", None, 2, 1, Path("unused.sqlite"), Path("unused"))
        with patch.object(Path, "mkdir") as mkdir, patch.object(bot.aiohttp, "ClientSession") as session:
            for value in values:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    Settings(*args, download_timeout=value)
            for value in (1, .25, 60.0):
                self.assertEqual(Settings(*args, download_timeout=value).download_timeout, value)
            mkdir.assert_not_called()
            session.assert_not_called()

    def test_invalid_worker_limits_rejected_before_process_or_path_io(self):
        values = (float("nan"), float("inf"), -float("inf"), True, False, None, "1", 0, -1)
        with patch.object(worker, "_run") as run, patch.object(worker.subprocess, "Popen") as process, \
             patch.object(Path, "resolve") as resolve:
            for name in ("deadline", "cpu_seconds", "memory_bytes", "output_bytes"):
                for value in values + ((1.5, 1.0) if name != "deadline" else ()):
                    with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                        worker.parse_replay_isolated(Path("unused"), **{name: value})
            run.assert_not_called()
            process.assert_not_called()
            resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
