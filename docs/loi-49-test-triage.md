# LOI-49: Triage of pre-existing unit-test failures

Command under triage:

```
pytest tests/ -m "not (requires_db or requires_gcs or slow or requires_tools)" -q
```

**Before:** 43 failed / 635 passed / 6 skipped / 383 deselected
**After:** 12 failed / 651 passed / 6 skipped / 398 deselected

(383 → 398 deselected because 15 tests that need a database or a live running
server were newly given `requires_db`, per bucket (d) below.)

## Buckets

- **(a) stale test** — asserts behavior the code intentionally changed
- **(b) broken import/fixture/collection artifact** — test infrastructure itself is wrong (bad mock target, incomplete fixture)
- **(c) genuine product bug** — the test correctly catches broken product behavior
- **(d) environment-dependent, mismarked** — needs `requires_db`/`requires_gcs`/a live server, wasn't marked
- **(e) unclear / needs product decision**

## pytest.ini / a2a hint

There is **no `pytest.ini`** in the repo — all pytest config lives in
`pyproject.toml`'s `[tool.pytest.ini_options]` (`testpaths=["tests"]`,
`asyncio_mode="auto"`, strict markers). That config is not broken: 12 of the
16 tests in `tests/a2a/test_task_audio_processing_integration.py` already
passed, and `asyncio_mode="auto"` correctly picks up async a2a tests with no
per-test `@pytest.mark.asyncio` needed. The actual cause of the a2a failures
was mundane — 4 tests in that file call `save_audio_metadata()` /
`get_connection()` directly against a real Postgres connection and were
simply never marked `requires_db` (see bucket (d) below). Whatever "pytest.ini
silently breaks a2a tests" referred to previously is not reproducible in the
current tree; recommend retiring that note.

## Full failure table (43)

| # | Test | Bucket | Root cause | Action |
|---|------|--------|------------|--------|
| 1 | `tests/a2a/test_task_audio_processing_integration.py::TestUUIDValidation::test_save_audio_metadata_accepts_valid_uuid` | (d) | Calls real `save_audio_metadata()` → real Postgres connection (`localhost:5432` refused); never marked `requires_db` | **Fixed**: added `@pytest.mark.requires_db` |
| 2 | `...TestDatabaseIntegration::test_save_audio_metadata_stores_a2a_task_id` | (d) | Same | **Fixed**: class-level `@pytest.mark.requires_db` on `TestDatabaseIntegration` |
| 3 | `...TestDatabaseIntegration::test_save_audio_metadata_allows_null_a2a_task_id` | (d) | Same | **Fixed** (covered by class marker) |
| 4 | `...TestDatabaseIntegration::test_database_schema_has_a2a_task_id_column` | (d) | Same | **Fixed** (covered by class marker) |
| 5 | `tests/integration/test_composer_artist_fallback.py::...::test_fallback_applied_in_pipeline` | (a) | `src/tools/process_audio.py` was refactored into a thin MCP adapter that delegates to `src.business.process_audio_shared`; none of the patched symbols (`extract_metadata_with_fallback`, `upload_audio_file`, `generate_signed_url`, etc.) exist on that module anymore | **Not fixed** — needs a real rewrite against `src/business/audio_processor.py`, out of scope for a trivial fix. Documented. |
| 6 | `...::test_mcp_resource_uses_fallback` | (a) | `get_metadata_resource()`'s URI regex only accepts hex UUIDs (`test-uuid` fails), *and* its real return shape (`{"uri","mimeType","text": json.dumps(...), "blob"}`) no longer matches the test's assertions (`result["id"]`, `result["Product"]`) — two independent staleness issues | **Not fixed** — needs a rewrite, out of scope. Documented. |
| 7 | `tests/test_exception_framework.py::TestFastMCPIntegration::test_setup_fastmcp_integration` | (b)/(c) | `@patch('src.exceptions_new.fastmcp_integration.get_mcp_instance')` fails because that name is never a module-level attribute — it's imported *inside* the function body from `..fastmcp_setup`. Worse: `src/fastmcp_setup.py` doesn't define `get_mcp_instance` at all, so in production `setup_fastmcp_exception_handling()` always hits `ImportError` and silently no-ops (caught by a broad `except ImportError`) | **Not fixed** — the correct patch target is ambiguous since the underlying function doesn't exist; fixing the test would just paper over dead code. Documented as a real finding (see below). |
| 8 | `...TestExceptionFrameworkIntegration::test_recovery_integration` | (a) | `ExceptionConfig().for_testing()` intentionally sets `enable_recovery=False` ("Disable recovery in tests for predictability"), so `response.recovery` is `{}` and has no `"retryable"` key | **Fixed**: test now does `config.enable_recovery = True` after `for_testing()` to opt back in, since this specific test exercises recovery |
| 9 | `tests/test_fastmcp_exception_serialization.py::...::test_fastmcp_tool_error_serialization` | (a) | FastMCP 2.12 removed the private `mcp._tools` attribute; public API is `await mcp.get_tools()` | **Fixed**: test now awaits `get_tools()` |
| 10 | `...::test_exception_hierarchy_preservation_task13` | (a) | Exception classes were intentionally moved from `src/exceptions.py` to `src/exceptions_core.py` (per CLAUDE.md); `src/exceptions/__init__.py` re-exports them for compatibility, but `type(exc).__module__` correctly reflects the real defining module | **Fixed**: assertion updated to `"src.exceptions_core"` |
| 11 | `tests/test_http_downloader.py::TestURLSchemeValidation::test_file_scheme_blocked` | (a) | `file` is in the explicit `BLOCKED_SCHEMES` denylist, which raises `"Blocked URL scheme '...'"`, not the generic `"Unsupported URL scheme"` message used for schemes that are simply not allowlisted | **Fixed**: regex updated to `"Blocked URL scheme"` |
| 12 | `...::test_ftp_scheme_blocked` | (a) | Same as #11 (`ftp` is also in `BLOCKED_SCHEMES`) | **Fixed** |
| 13 | `...TestErrorHandling::test_size_exceeded_during_download` | (c) | **Genuine bug.** `http_downloader.py`'s `download()` raises `DownloadSizeError` (a `DownloadError` subclass) inside the download loop, but a trailing `except Exception as e: raise DownloadError(...)` catches it before any caller can distinguish it, silently discarding the typed-exception contract | **Not fixed** (product bug, not a test bug) — documented below |
| 14–24 | `tests/test_mcp_protocol.py::test_mcp_handshake`, `test_mcp_tools_list`, `test_mcp_tools_call_health_check`, `test_mcp_tools_call_invalid_tool`, `test_mcp_tools_call_process_audio_complete`, `test_mcp_tools_call_search_library`, `test_mcp_tools_call_update_metadata`, `test_mcp_tools_call_delete_audio`, `test_mcp_prompts_list`, `test_mcp_prompt_execution`, `test_mcp_resources_list` (11 tests) | (d) | Every test opens a `fastmcp.Client("http://localhost:8080/mcp")` — this is a live-server E2E suite, not a unit test; there's no server listening | **Fixed**: added `test_mcp_protocol.py` to `conftest.py`'s `requires_db` file list (matches an existing pattern for "needs external infra") |
| 25–32 | `tests/test_multi_format_support.py` — `TestMP3FormatSupport::test_mp3_id3v2_extraction`, `test_mp3_id3v23_tyer_tag`, `TestFLACFormatSupport::test_flac_vorbis_comments`, `TestM4AFormatSupport::test_m4a_mp4_tags`, `TestOGGFormatSupport::test_ogg_vorbis_comments`, `TestWAVFormatSupport::test_wav_riff_info`, `TestFormatDetectionAndValidation::test_supported_formats_list`, `TestCrossFormatFeatures::test_technical_specs_extraction_all_formats` (8 tests) | (b)/(a) | `src/metadata/extractor.py` does `from mutagen import File as MutagenFile` / `from mutagen.mp3 import MP3` etc. (names bound into its own module), but the tests patched `mutagen.File`, `mutagen.mp3.MP3`, ... — the wrong target, so the mocks never took effect and the extractor ran real mutagen parsing against fake byte strings like `b"fake mp3"`, producing real parser errors. Separately, `test_supported_formats_list`'s expected set was missing `.aif`/`.aiff`, which were intentionally added to `SUPPORTED_FORMATS` | **Fixed**: repointed all `@patch(...)` decorators at `src.metadata.extractor.<Name>`; updated the expected-formats set; added a missing `mock_audio.info.bitrate` and switched WAV's `info` mock to `Mock(spec=[...])` so `hasattr()` checks reflect a real WAV info object instead of auto-vivifying every attribute name |
| 33 | `tests/test_regression_tasks_13_14.py::TestFastMCPExceptionSerialization::test_exception_hierarchy_preservation` | (a) | Same module-rename issue as #10 | **Fixed**: assertion updated to `"src.exceptions_core"` |
| 34 | `tests/test_search_filter_parser.py::TestFilterValidation::test_like_operator` | (a) | The RSQL parser intentionally strips `*` wildcards at parse time (`value_str.strip('*')`); the repository/SQL layer re-adds `%...%` itself when building the `ILIKE` clause (see `database/operations.py`, e.g. `f"%{composer_filter}%"`) | **Fixed**: expected value updated to `"beatles"` (no wildcards) |
| 35–40 | `tests/test_ssrf_protection.py::TestSSRFURLValidation::test_private_ip_blocked`, `test_localhost_blocked`, `test_link_local_blocked`, `TestConvenienceFunctions::test_validate_ssrf_blocks_private`, `TestURLValidation::test_validate_url_with_private_ip_blocked`, `TestErrorMessages::test_private_ip_error_message` (6 tests) | (c) | **Genuine security bug — see verdict below.** | **Not fixed** (would require product-code change) — documented, flagged as the most important finding |
| 41 | `tests/test_url_validators.py::TestURLSchemeValidation::test_ws_scheme_blocked` | (a) | `ws` is in `BLOCKED_SCHEMES` (same pattern as #11/#12); sibling test `test_javascript_scheme_blocked` already correctly expects `"Blocked URL scheme"` | **Fixed**: regex updated to `"Blocked URL scheme"` |
| 42 | `...TestEdgeCases::test_url_with_credentials_allowed` | (c) | **Genuine bug.** `validators.py::validate_hostname()` does `hostname = parsed.netloc.split(':')[0]`. For `https://user:pass@example.com/...`, `netloc` is `"user:pass@example.com"`, so `.split(':')[0]` yields `"user"` — the userinfo, not the host — which then fails the FQDN check | **Not fixed** (product bug) — documented below |
| 43 | `...TestEdgeCases::test_ipv6_hostname_allowed` | (c) | Same root cause as #42: `netloc.split(':')[0]` on `"[2001:db8::1]"` splits on the colons *inside* the IPv6 literal and yields `"[2001"` | **Not fixed** (product bug) — documented below |

## SSRF verdict (explicit, as requested)

**This is a genuine product bug, not a stale test — and it's a real bypass, though its practical blast radius is limited by how the one production caller uses the function today.**

`src/downloader/ssrf_protection.py`:

```python
class SSRFProtectionError(ValueError):
    ...

@staticmethod
def validate_url(url: str, check_dns: bool = True) -> None:
    ...
    try:
        ip = ipaddress.ip_address(hostname)
        if SSRFProtector.is_private_ip(hostname):
            raise SSRFProtectionError(f"Access to private IP address {hostname} is blocked...")
        ...
    except ValueError:
        # Not an IP address, it's a hostname
        if check_dns:
            try:
                resolved_ips = SSRFProtector.resolve_hostname(hostname)
                for ip_str in resolved_ips:
                    if SSRFProtector.is_private_ip(ip_str):
                        raise SSRFProtectionError(...)
            except socket.gaierror:
                pass
```

`SSRFProtectionError` subclasses `ValueError`. When `hostname` is a literal
private IP (e.g. `192.168.1.1`), `is_private_ip()` raises
`SSRFProtectionError` *inside the same `try` block* that catches
`ValueError` — so the protection error is immediately swallowed by its own
`except ValueError:` clause and misinterpreted as "not an IP, must be a
hostname." Execution then falls into the `if check_dns:` branch:

- With `check_dns=False` (every failing test above), that branch is skipped
  entirely and `validate_url()` returns normally — **the private IP passes
  validation with zero protection.**
- With `check_dns=True` (the default, and what every current production
  caller uses — `src/downloader/http_downloader.py:212`,
  `src/a2a_server/message_parser.py:148`, `src/business/audio_processor.py:305`),
  the code calls `resolve_hostname()`, which calls `socket.getaddrinfo()` on
  the IP literal. `getaddrinfo` resolves numeric IPs locally without any
  network access and returns the same IP, so the second `is_private_ip()`
  check (inside the *inner* `try/except socket.gaierror`, which does **not**
  catch `ValueError`) fires correctly and `SSRFProtectionError` propagates as
  expected. This is why `test_downloader_blocks_private_ip` and friends
  (which exercise the real `HTTPDownloader.download()` path) still pass.

So today, every real call site happens to be protected — but only by
accident, via a second, unrelated code path (DNS-resolving an IP literal
back to itself) rather than by design. `check_dns=False` is a legitimate,
documented parameter (used for fast pre-validation without a DNS round
trip), and any future caller — or `validate_ssrf()`/`SSRFProtector.validate_url()`
called directly with `check_dns=False` — gets **zero** SSRF protection for
IP-literal URLs. The exception hierarchy itself (`SSRFProtectionError(ValueError)`)
is the root defect: any `try/except ValueError` wrapping code that raises
`SSRFProtectionError` will accidentally swallow it. Recommend (not applied
here, per triage scope): stop subclassing `ValueError`, or restructure
`validate_url()` so the private-IP check for literal IPs sits outside the
`except ValueError:` block.

## Other genuine product bugs found

1. **SSRF protection bypass with `check_dns=False`** (above) — the most
   important finding.
2. **`validate_hostname()` mis-parses `netloc`** (`src/downloader/validators.py:144`,
   `hostname = parsed.netloc.split(':')[0]`) — breaks legitimate URLs with
   `user:pass@host` credentials (extracts `"user"` instead of the host) and
   breaks IPv6 literal hosts entirely (splits on colons inside the address).
   Should use `urlparse(url).hostname` instead, which handles both cases
   correctly. Net effect today is *over-rejection* of valid URLs, not a
   security hole, but it's a real, user-facing bug in URL parsing.
3. **`DownloadSizeError` is swallowed into generic `DownloadError`**
   (`src/downloader/http_downloader.py`'s `download()`) — the trailing
   `except Exception as e: raise DownloadError(...)` re-wraps a more specific,
   already-typed `DownloadSizeError` (and any other typed error raised inside
   that block), breaking the documented typed-exception contract for callers
   that want to special-case "file too large" vs. generic failures.
4. **`setup_fastmcp_exception_handling()` is dead code** (`src/exceptions_new/fastmcp_integration.py`) —
   it imports `get_mcp_instance` from `src.fastmcp_setup`, but that function
   doesn't exist there (checked: `src/fastmcp_setup.py` only defines
   `create_fastmcp_server`, `setup_jinja_templates`, `get_server_config`,
   `validate_server_setup`, `log_server_startup_info`). Every call hits
   `ImportError` and is silently swallowed by a broad `except ImportError:
   logger.warning(...)`, so this integration path has likely never actually
   run. Low severity (no crash, just a no-op), but worth cleaning up or
   removing.

None of these were fixed in this branch — per the triage instructions, only
trivially-fixable test issues (wrong imports/patch targets, renamed symbols,
missing markers, stale fixtures/assertions) were fixed. All four are product
code and are documented here for a follow-up ticket.
