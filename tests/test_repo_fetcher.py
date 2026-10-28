"""Tests for the platform repo-fetch layer (mira.platforms.fetch)."""

from __future__ import annotations

import asyncio
import io
import tarfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mira.platforms import fetch
from mira.platforms.fetch import (
    EmptyRepoError,
    ForgejoRepoFetcher,
    GitHubRepoFetcher,
    GitLabRepoFetcher,
    IncompleteTreeError,
    _strip_tarball,
    make_fetcher,
)


def _make_targz(prefix: str, files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for path, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=f"{prefix}/{path}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetcher_type", [GitHubRepoFetcher, GitLabRepoFetcher, ForgejoRepoFetcher])
@pytest.mark.parametrize("indexable_paths", [None, set(), {"src/keep.py"}])
async def test_tarball_filters_excluded_paths(monkeypatch, fetcher_type, indexable_paths):
    blob = _make_targz("synthetic-root", {"src/keep.py": "kept", "vendor/skip.py": "skipped"})
    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=blob))
    monkeypatch.setattr(
        fetch.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=transport, **kwargs),
    )

    result = await fetcher_type("synthetic", "https://provider.example.invalid/api").repo_tarball(
        "example", "app", "main", indexable_paths=indexable_paths
    )

    files = {"src/keep.py": "kept", "vendor/skip.py": "skipped"}
    expected = files if indexable_paths is None else {p: files[p] for p in indexable_paths}
    assert result == expected


class TestStripTarball:
    def test_strips_top_level_dir(self):
        blob = _make_targz("acme-web-abc123", {"src/main.py": "x = 1", "README.md": "# hi"})
        out = _strip_tarball(blob, max_file_size=1_048_576, label="acme/web")
        assert out == {"src/main.py": "x = 1", "README.md": "# hi"}

    def test_gitlab_prefix_shape(self):
        # GitLab archives wrap as {repo}-{ref}-{sha}/ — still a single top dir.
        blob = _make_targz("web-main-deadbeef", {"a.py": "1"})
        assert _strip_tarball(blob, 1_048_576, "g/web") == {"a.py": "1"}

    def test_size_limit_skips_large(self):
        blob = _make_targz("r-sha", {"big.py": "y" * 50})
        assert _strip_tarball(blob, max_file_size=10, label="o/r") == {}


def _resp(json_data=None, *, text="", headers=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    r.text = text
    r.headers = headers or {}
    r.raise_for_status = MagicMock()
    return r


def _patch_client(get_side_effect):
    client = AsyncMock()
    client.get = AsyncMock(side_effect=get_side_effect)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("mira.platforms.fetch.httpx.AsyncClient", return_value=client)


@pytest.mark.asyncio
@pytest.mark.parametrize("fetcher", [GitHubRepoFetcher, GitLabRepoFetcher, ForgejoRepoFetcher])
@pytest.mark.parametrize(
    "ref",
    [
        "main",
        "feature/topic",
        "feature+draft",
        "feature&mode=bad",
        "feature#frag",
        "feature%2Bdraft",
    ],
)
async def test_file_content_preserves_ref(fetcher, ref):
    requests = []

    def serve(request):
        requests.append(request)
        if fetcher is ForgejoRepoFetcher:
            return httpx.Response(200, json={"content": "c3ludGhldGljIGNvbnRlbnQ="})
        return httpx.Response(200, text="synthetic content")

    client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    with patch("mira.platforms.fetch.httpx.AsyncClient", return_value=client):
        content = await fetcher("synthetic", "https://forge.example.invalid/api").file_content(
            "example", "app", "src/main.py", ref
        )

    assert content == "synthetic content"
    assert len(requests) == 1
    assert requests[0].url.params.multi_items() == [("ref", ref)]
    assert requests[0].url.fragment == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "encoded_path"),
    [
        ("src/hash#name.py", b"src/hash%23name.py"),
        ("src/question?name.py", b"src/question%3Fname.py"),
        ("src/literal%2Fname.py", b"src/literal%252Fname.py"),
        ("src/nested/main.py", b"src/nested/main.py"),
    ],
)
async def test_github_file_content_preserves_path(path, encoded_path):
    requests = []

    def serve(request):
        requests.append(request)
        return httpx.Response(200, text="synthetic content")

    client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    with patch("mira.platforms.fetch.httpx.AsyncClient", return_value=client):
        content = await GitHubRepoFetcher(
            "synthetic", "https://github.example.invalid/api"
        ).file_content("example", "app", path, "main")

    assert content == "synthetic content"
    assert len(requests) == 1
    assert (
        requests[0].url.raw_path
        == b"/api/repos/example/app/contents/" + encoded_path + b"?ref=main"
    )
    assert requests[0].url.params.multi_items() == [("ref", "main")]
    assert requests[0].url.fragment == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fetcher", "encoded_path"),
    [
        (
            GitLabRepoFetcher,
            b"/api/projects/example%2Fapp/repository/files/src%2Fa%23b%3Fc%252F.py/raw",
        ),
        (ForgejoRepoFetcher, b"/api/repos/example/app/contents/src%2Fa%23b%3Fc%252F.py"),
    ],
)
async def test_file_content_retains_encoded_path(fetcher, encoded_path):
    requests = []

    def serve(request):
        requests.append(request)
        if fetcher is ForgejoRepoFetcher:
            return httpx.Response(200, json={"content": "c3ludGhldGljIGNvbnRlbnQ="})
        return httpx.Response(200, text="synthetic content")

    client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    with patch("mira.platforms.fetch.httpx.AsyncClient", return_value=client):
        content = await fetcher("synthetic", "https://forge.example.invalid/api").file_content(
            "example", "app", "src/a#b?c%2F.py", "feature/topic"
        )

    assert content == "synthetic content"
    assert len(requests) == 1
    assert requests[0].url.raw_path == encoded_path + b"?ref=feature%2Ftopic"
    assert requests[0].url.params.multi_items() == [("ref", "feature/topic")]
    assert requests[0].url.fragment == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("fetcher", [GitHubRepoFetcher, GitLabRepoFetcher, ForgejoRepoFetcher])
@pytest.mark.parametrize("outcome", [404, 503, "timeout"])
async def test_file_content_failure_returns_none_and_releases_semaphore(fetcher, outcome):
    semaphore = asyncio.Semaphore(1)
    acquired = []

    def serve(request):
        acquired.append(semaphore.locked())
        if outcome == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(outcome)

    client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    with patch("mira.platforms.fetch.httpx.AsyncClient", return_value=client):
        content = await fetcher("synthetic", "https://forge.example.invalid/api").file_content(
            "example", "app", "src/main.py", "feature+draft", semaphore
        )

    assert content is None
    assert acquired == [True]
    assert not semaphore.locked()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetcher", [GitHubRepoFetcher, GitLabRepoFetcher, ForgejoRepoFetcher])
async def test_file_content_success_releases_semaphore(fetcher):
    semaphore = asyncio.Semaphore(1)
    acquired = []

    def serve(request):
        acquired.append(semaphore.locked())
        if fetcher is ForgejoRepoFetcher:
            return httpx.Response(200, json={"content": "c3ludGhldGljIGNvbnRlbnQ="})
        return httpx.Response(200, text="synthetic content")

    client = httpx.AsyncClient(transport=httpx.MockTransport(serve))
    with patch("mira.platforms.fetch.httpx.AsyncClient", return_value=client):
        content = await fetcher("synthetic", "https://forge.example.invalid/api").file_content(
            "example", "app", "src/main.py", "feature+draft", semaphore
        )

    assert content == "synthetic content"
    assert acquired == [True]
    assert not semaphore.locked()


class TestGitLabTreePagination:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "change",
        [
            {"ref": "other"},
            {"recursive": "false"},
            {"per_page": "1"},
            {"pagination": "offset"},
            {"path": "subdir"},
            {"ref": None},
        ],
    )
    async def test_rejects_next_link_that_changes_tree_query(self, change):
        endpoint = "https://gitlab.example.invalid/api/v4/projects/example%2Fapp/repository/tree"
        params = {
            "recursive": "true",
            "per_page": "100",
            "pagination": "keyset",
            "ref": "main",
            "page_token": "next",
        }
        for key, value in change.items():
            if value is None:
                params.pop(key)
            else:
                params[key] = value
        next_url = httpx.URL(endpoint, params=params)
        pages = [
            _resp(
                [{"type": "blob", "path": "a.py"}], headers={"link": f'<{next_url}>; rel="next"'}
            ),
            _resp([{"type": "blob", "path": "b.py"}]),
        ]
        with _patch_client(pages), pytest.raises(IncompleteTreeError):
            await GitLabRepoFetcher("synthetic", "https://gitlab.example.invalid/api/v4").repo_tree(
                "example", "app", "main"
            )

    @pytest.mark.asyncio
    async def test_follows_keyset_link(self):
        page1 = _resp(
            [{"type": "blob", "path": "a.py"}, {"type": "tree", "path": "sub"}],
            headers={
                "link": '<https://gitlab.com/api/v4/projects/grp%2Fsub%2Fproj/repository/tree?recursive=true&per_page=100&pagination=keyset&ref=main&page_token=next>; rel="next"'
            },
        )
        page2 = _resp([{"type": "blob", "path": "sub/b.py"}], headers={})
        with _patch_client([page1, page2]):
            paths = await GitLabRepoFetcher("tok").repo_tree("grp/sub", "proj", "main")
        assert paths == ["a.py", "sub/b.py"]

    @pytest.mark.asyncio
    async def test_url_encodes_nested_project(self):
        captured = {}

        async def grab(url, **kw):
            captured["url"] = url
            return _resp([], headers={})

        with _patch_client(grab):
            await GitLabRepoFetcher("tok").repo_tree("group/sub", "web", "main")
        assert "group%2Fsub%2Fweb" in captured["url"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "next_link",
        [
            "not-a-link",
            'https://gitlab.example.invalid/api/v4/projects/example%2Fapp/repository/tree; rel="next"',
            '<https://other.example.invalid/tree>; rel="next"',
            '<https://gitlab.example.invalid/api/v4/unrelated>; rel="next"',
            '<https://user@gitlab.example.invalid/api/v4/projects/example%2Fapp/repository/tree>; rel="next"',
        ],
    )
    async def test_rejects_invalid_next_link_before_request(self, next_link):
        requested = 0

        async def serve(url, **kwargs):
            nonlocal requested
            requested += 1
            if requested > 1:
                pytest.fail("Followed an invalid pagination link")
            return _resp([{"type": "blob", "path": "a.py"}], headers={"link": next_link})

        with _patch_client(serve), pytest.raises(IncompleteTreeError):
            await GitLabRepoFetcher("synthetic", "https://gitlab.example.invalid/api/v4").repo_tree(
                "example", "app", "main"
            )
        assert requested == 1

    @pytest.mark.asyncio
    async def test_rejects_cyclic_pagination_before_repeating_request(self):
        endpoint = "https://gitlab.example.invalid/api/v4/projects/example%2Fapp/repository/tree"
        initial = endpoint + "?recursive=true&per_page=100&pagination=keyset&ref=main"
        pages = [
            _resp(
                [{"type": "blob", "path": "a.py"}],
                headers={
                    "link": f'<{endpoint}?recursive=true&per_page=100&pagination=keyset&ref=main&page_token=next>; rel="next"'
                },
            ),
            _resp(
                [{"type": "blob", "path": "b.py"}],
                headers={"link": f'<{initial}&page_token=last>; rel="next"'},
            ),
            _resp(
                [{"type": "blob", "path": "c.py"}],
                headers={"link": f'<{initial}&page_token=next>; rel="next"'},
            ),
        ]
        requested = 0

        async def serve(url, **kwargs):
            nonlocal requested
            requested += 1
            if requested > len(pages):
                pytest.fail("Repeated a tree page request")
            return pages[requested - 1]

        with _patch_client(serve), pytest.raises(IncompleteTreeError, match="cyclic"):
            await GitLabRepoFetcher("synthetic", "https://gitlab.example.invalid/api/v4").repo_tree(
                "example", "app", "main"
            )
        assert requested == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "pages",
        [
            [_resp({})],
            [_resp([{"type": "blob"}])],
            [
                _resp(
                    [],
                    headers={
                        "link": '<https://gitlab.com/api/v4/projects/o%2Fr/repository/tree?recursive=true&per_page=100&pagination=keyset&ref=main&page_token=2>; rel="next"'
                    },
                )
            ],
            [
                _resp(
                    [{"type": "blob", "path": "a.py"}],
                    headers={
                        "link": '<https://gitlab.com/api/v4/projects/o%2Fr/repository/tree?recursive=true&per_page=100&pagination=keyset&ref=main&page_token=2>; rel="next"'
                    },
                ),
                _resp([{"type": "blob", "path": "a.py"}]),
            ],
        ],
    )
    async def test_rejects_invalid_or_repeated_entries(self, pages):
        with _patch_client(pages), pytest.raises(IncompleteTreeError):
            await GitLabRepoFetcher("synthetic").repo_tree("o", "r", "main")

    @pytest.mark.asyncio
    async def test_bounds_page_requests(self, monkeypatch):
        monkeypatch.setattr(fetch, "_MAX_TREE_PAGES", 2)
        endpoint = "https://gitlab.com/api/v4/projects/o%2Fr/repository/tree"
        requested = 0

        async def serve(url, **kwargs):
            nonlocal requested
            requested += 1
            if requested > 2:
                pytest.fail("Exceeded the tree page limit")
            return _resp(
                [{"type": "blob", "path": f"a{requested}.py"}],
                headers={
                    "link": f'<{endpoint}?recursive=true&per_page=100&pagination=keyset&ref=main&page_token={requested + 1}>; rel="next"'
                },
            )

        with _patch_client(serve), pytest.raises(IncompleteTreeError, match="limit"):
            await GitLabRepoFetcher("synthetic").repo_tree("o", "r", "main")
        assert requested == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("fetcher", [GitHubRepoFetcher, GitLabRepoFetcher, ForgejoRepoFetcher])
async def test_invalid_tree_json_is_explicit_fetch_error(fetcher):
    response = _resp()
    response.json.side_effect = ValueError("synthetic invalid JSON")
    with _patch_client([response]), pytest.raises(IncompleteTreeError):
        await fetcher("synthetic").repo_tree("example", "app", "main")


@pytest.mark.asyncio
@pytest.mark.parametrize("fetcher", [GitHubRepoFetcher, GitLabRepoFetcher, ForgejoRepoFetcher])
async def test_tree_http_error_is_not_an_empty_or_partial_list(fetcher):
    response = httpx.Response(503, request=httpx.Request("GET", "https://example.invalid/tree"))
    with _patch_client([response]), pytest.raises(httpx.HTTPStatusError):
        await fetcher("synthetic").repo_tree("example", "app", "main")


@pytest.mark.asyncio
@pytest.mark.parametrize("fetcher", [GitHubRepoFetcher, GitLabRepoFetcher, ForgejoRepoFetcher])
async def test_tree_timeout_is_not_an_empty_or_partial_list(fetcher):
    with _patch_client(httpx.ReadTimeout("synthetic timeout")), pytest.raises(httpx.ReadTimeout):
        await fetcher("synthetic").repo_tree("example", "app", "main")


class TestEmptyRepo:
    @pytest.mark.asyncio
    async def test_gitlab_tree_404_raises_empty(self):
        with (
            _patch_client(lambda url, **kw: _resp(status=404, text="404 Tree Not Found")),
            pytest.raises(EmptyRepoError),
        ):
            await GitLabRepoFetcher("t").repo_tree("g", "p", "main")

    @pytest.mark.asyncio
    async def test_github_tree_409_raises_empty(self):
        with (
            _patch_client(lambda url, **kw: _resp(status=409, text="empty")),
            pytest.raises(EmptyRepoError),
        ):
            await GitHubRepoFetcher("t").repo_tree("o", "r", "main")


class TestGitHubTreeCompleteness:
    @pytest.mark.asyncio
    async def test_rejects_truncated_tree(self):
        partial = _resp({"tree": [{"type": "blob", "path": "a.py"}], "truncated": True})
        with _patch_client([partial]), pytest.raises(IncompleteTreeError, match="incomplete"):
            await GitHubRepoFetcher("synthetic").repo_tree("example", "app", "main")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"tree": []},
            {"tree": [], "truncated": "false"},
            {"tree": None, "truncated": False},
            {"tree": [{"type": "blob"}], "truncated": False},
            {"tree": [{"type": "unknown", "path": "a"}], "truncated": False},
            {"tree": [{"type": "blob", "path": ""}], "truncated": False},
            {"tree": [None], "truncated": False},
            {
                "tree": [{"type": "blob", "path": "a.py"}] * 2,
                "truncated": False,
            },
        ],
    )
    async def test_rejects_unverifiable_response(self, data):
        with _patch_client([_resp(data)]), pytest.raises(IncompleteTreeError):
            await GitHubRepoFetcher("synthetic").repo_tree("example", "app", "main")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "entries",
        [
            [],
            [
                {"type": "tree", "path": "src"},
                {"type": "blob", "path": "src/a.py"},
                {"type": "commit", "path": "vendor/submodule"},
            ],
        ],
    )
    async def test_complete_tree_returns_only_files(self, entries):
        with _patch_client([_resp({"tree": entries, "truncated": False})]):
            paths = await GitHubRepoFetcher("synthetic").repo_tree("example", "app", "main")
        assert paths == [entry["path"] for entry in entries if entry["type"] == "blob"]


class TestForgejoTreeCompleteness:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "entries",
        [
            [],
            [
                {"type": "tree", "path": "src"},
                {"type": "blob", "path": "src/a.py"},
                {"type": "commit", "path": "vendor/submodule"},
            ],
        ],
    )
    async def test_complete_single_page(self, entries):
        page = {"tree": entries, "total_count": len(entries), "truncated": False}
        with _patch_client([_resp(page)]):
            paths = await ForgejoRepoFetcher("synthetic").repo_tree("example", "app", "main")
        assert paths == [entry["path"] for entry in entries if entry["type"] == "blob"]

    @pytest.mark.asyncio
    async def test_preserves_empty_repository_error(self):
        with _patch_client([_resp(status=404)]), pytest.raises(EmptyRepoError):
            await ForgejoRepoFetcher("synthetic").repo_tree("example", "app", "main")

    @pytest.mark.asyncio
    async def test_stops_at_total_count_even_when_truncated_stays_true(self):
        entries = [{"type": "tree", "path": f"dir{i}"} for i in range(99)]
        entries.append({"type": "blob", "path": "a.py"})
        pages = [
            {"tree": entries, "total_count": 101, "truncated": True},
            {"tree": [{"type": "blob", "path": "b.py"}], "total_count": 101, "truncated": True},
        ]
        requested = []

        async def serve(url, **kwargs):
            requested.append(url)
            if len(requested) > len(pages):
                pytest.fail("Requested a page after receiving the complete tree")
            return _resp(pages[len(requested) - 1])

        with _patch_client(serve):
            paths = await ForgejoRepoFetcher("synthetic").repo_tree("example", "app", "main")
        assert paths == ["a.py", "b.py"]
        assert len(requested) == 2
        assert "per_page=100" in requested[0]
        assert "page=2" in requested[1]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "pages",
        [
            [{"tree": [], "truncated": False}],
            [{"tree": [], "total_count": False, "truncated": False}],
            [{"tree": [], "total_count": -1, "truncated": False}],
            [{"tree": [], "total_count": 0.0, "truncated": False}],
            [{"tree": [], "total_count": 0}],
            [{"tree": [], "total_count": 1, "truncated": True}],
            [{"tree": [{"path": "a.py", "type": "blob"}], "total_count": 0, "truncated": False}],
            [{"tree": [{"path": "a.py", "type": "blob"}], "total_count": 2, "truncated": False}],
            [
                {"tree": [{"path": "a.py", "type": "blob"}], "total_count": 2, "truncated": True},
                {"tree": [{"path": "b.py", "type": "blob"}], "total_count": 3, "truncated": True},
            ],
            [
                {"tree": [{"path": "a.py", "type": "blob"}], "total_count": 2, "truncated": True},
                {"tree": [{"path": "a.py", "type": "blob"}], "total_count": 2, "truncated": True},
            ],
        ],
    )
    async def test_rejects_inconsistent_or_nonprogressing_pages(self, pages):
        requested = 0

        async def serve(url, **kwargs):
            nonlocal requested
            requested += 1
            if requested > len(pages):
                pytest.fail("Continued fetching after an invalid tree page")
            return _resp(pages[requested - 1])

        with _patch_client(serve), pytest.raises(IncompleteTreeError):
            await ForgejoRepoFetcher("synthetic").repo_tree("example", "app", "main")

    @pytest.mark.asyncio
    async def test_bounds_page_requests(self, monkeypatch):
        monkeypatch.setattr(fetch, "_MAX_TREE_PAGES", 2)
        requested = 0

        async def serve(url, **kwargs):
            nonlocal requested
            requested += 1
            if requested > 2:
                pytest.fail("Exceeded the tree page limit")
            return _resp(
                {
                    "tree": [{"type": "blob", "path": f"a{requested}.py"}],
                    "total_count": 3,
                    "truncated": True,
                }
            )

        with _patch_client(serve), pytest.raises(IncompleteTreeError, match="limit"):
            await ForgejoRepoFetcher("synthetic").repo_tree("example", "app", "main")
        assert requested == 2


class TestMakeFetcher:
    def test_github(self):
        assert isinstance(make_fetcher("github", "t"), GitHubRepoFetcher)

    def test_gitlab(self):
        f = make_fetcher("gitlab", "t")
        assert isinstance(f, GitLabRepoFetcher)
