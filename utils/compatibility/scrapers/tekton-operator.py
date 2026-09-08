"""Generate Tekton Operator compatibility rows from first-party release metadata.

Source policy:
- Kubernetes compatibility comes from tektoncd/operator's README release tables,
  where each Operator release series publishes a minimum Kubernetes minor.
- Exact application/chart versions are accepted only when GitHub publishes BOTH
  the normal ``vX.Y.Z`` Operator release and the paired
  ``tekton-operator-X.Y.Z`` Helm-chart release.
- A documented minimum is expanded only through Plural's current KUBE_VERSION.
  This records the upstream installation lower bound, not independent testing of
  every intermediate Kubernetes minor.
"""

from __future__ import annotations

from collections import OrderedDict
import re
from typing import Iterable

from packaging.version import Version
import requests

from utils import current_kube_version, fetch_page, print_error, update_compatibility_info

APP_NAME = "tekton-operator"
README_URL = "https://raw.githubusercontent.com/tektoncd/operator/main/README.md"
RELEASES_URL = "https://api.github.com/repos/tektoncd/operator/releases"
TARGET_FILE = "../../static/compatibilities/tekton-operator.yaml"
OCI_MIN_VERSION = Version("0.80.0")

_SERIES_ROW_RE = re.compile(
    r"^\|\s*v(?P<series>\d+\.\d+)\.x(?:\s+LTS)?\s*\|\s*"
    r"(?P<kube>\d+\.\d+)\.x\s*\|",
    re.IGNORECASE,
)
_RUNTIME_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")
_CHART_TAG_RE = re.compile(r"^tekton-operator-(?P<version>\d+\.\d+\.\d+)$")


def _decode(content: bytes | str) -> str:
    if isinstance(content, str):
        return content
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Could not decode Tekton Operator README as UTF-8") from exc


def parse_minimum_kubernetes(content: bytes | str) -> dict[str, str]:
    """Return ``operator major.minor -> minimum Kubernetes major.minor``.

    Both the current-support and EOL tables are parsed so the scraper can retain
    all documented historical series. Conflicting duplicate rows fail closed.
    """

    text = _decode(content)
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        match = _SERIES_ROW_RE.match(raw_line.strip())
        if not match:
            continue
        series = match.group("series")
        kube = match.group("kube")
        if series in result and result[series] != kube:
            raise ValueError(
                f"Conflicting Kubernetes minimums for Tekton Operator {series}.x"
            )
        result[series] = kube

    if not result:
        raise ValueError("Tekton Operator release compatibility table not found")
    return result


def parse_release_records(pages: Iterable[list[dict]]) -> set[str]:
    """Return exact stable versions that have both runtime and Helm releases."""

    runtime: set[str] = set()
    charts: set[str] = set()

    for page in pages:
        if not isinstance(page, list):
            raise ValueError("Unexpected Tekton Operator releases API response")
        for release in page:
            if not isinstance(release, dict):
                raise ValueError("Unexpected Tekton Operator release record")
            if release.get("draft") or release.get("prerelease"):
                continue
            tag = release.get("tag_name")
            if not isinstance(tag, str):
                continue
            runtime_match = _RUNTIME_TAG_RE.fullmatch(tag)
            chart_match = _CHART_TAG_RE.fullmatch(tag)
            if runtime_match:
                runtime.add(runtime_match.group("version"))
            elif chart_match:
                charts.add(chart_match.group("version"))

    return runtime & charts


def expand_lower_bound(start: str, end: str) -> list[str]:
    """Expand an inclusive Kubernetes minor lower bound, newest first."""

    try:
        start_major, start_minor = (int(v) for v in start.split("."))
        end_major, end_minor = (int(v) for v in end.split("."))
    except Exception as exc:
        raise ValueError("Invalid Kubernetes minor version") from exc

    if start_major != end_major or start_minor > end_minor:
        raise ValueError(
            f"Unsupported Kubernetes range for Tekton Operator: {start} -> {end}"
        )
    return [f"{start_major}.{minor}" for minor in range(end_minor, start_minor - 1, -1)]


def build_rows(
    minimums: dict[str, str],
    exact_versions: set[str],
    kube_max: str,
) -> list[OrderedDict[str, object]]:
    """Select the latest exact chart-backed patch for every documented series."""

    by_series: dict[str, list[str]] = {}
    for version in exact_versions:
        try:
            parsed = Version(version)
        except Exception as exc:
            raise ValueError(f"Invalid Tekton Operator release version: {version}") from exc
        if parsed.pre or parsed.dev or parsed.local or parsed < OCI_MIN_VERSION:
            # The current official OCI chart repository starts at v0.80.0.
            # Older chart assets existed, but the retired git-based install path
            # is no longer a usable Helm repository for Plural.
            continue
        series = f"{parsed.major}.{parsed.minor}"
        if series in minimums:
            by_series.setdefault(series, []).append(version)

    rows: list[OrderedDict[str, object]] = []
    for series, min_kube in minimums.items():
        candidates = by_series.get(series, [])
        if not candidates:
            # Older documented releases can predate the published Helm chart.
            # Skipping them is safer than inventing chart metadata.
            continue
        latest = max(candidates, key=Version)
        rows.append(
            OrderedDict(
                [
                    ("version", latest),
                    ("kube", expand_lower_bound(min_kube, kube_max)),
                    ("requirements", []),
                    ("incompatibilities", []),
                    ("chart_version", latest),
                ]
            )
        )

    if not rows:
        raise ValueError("No chart-backed Tekton Operator releases matched the compatibility table")

    rows.sort(key=lambda row: Version(str(row["version"])), reverse=True)
    return rows


def fetch_release_pages(max_pages: int = 10) -> list[list[dict]]:
    pages: list[list[dict]] = []
    for page in range(1, max_pages + 1):
        response = requests.get(
            RELEASES_URL,
            params={"per_page": 100, "page": page},
            timeout=20,
            headers={"Accept": "application/vnd.github+json"},
        )
        if response.status_code != 200:
            raise ValueError(
                f"Tekton Operator releases API returned HTTP {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected Tekton Operator releases API response")
        if not payload:
            break
        pages.append(payload)
        if len(payload) < 100:
            break
    if not pages:
        raise ValueError("Tekton Operator releases API returned no releases")
    return pages


def scrape() -> None:
    try:
        readme = fetch_page(README_URL)
        if not readme:
            raise ValueError("Failed to fetch Tekton Operator README")
        minimums = parse_minimum_kubernetes(readme)
        exact_versions = parse_release_records(fetch_release_pages())
        kube_max = current_kube_version()
        if not kube_max:
            raise ValueError("Plural KUBE_VERSION is unavailable")
        rows = build_rows(minimums, exact_versions, kube_max)
        update_compatibility_info(TARGET_FILE, rows)
    except Exception as exc:
        print_error(str(exc))


if __name__ == "__main__":
    scrape()
