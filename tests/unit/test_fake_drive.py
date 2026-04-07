"""FakeDrive — verifies the test double behaves like the bits of Drive we use.

If FakeDrive lies, every GoogleDriveStorage test built on it lies. Pin the
behavior we depend on.
"""

from __future__ import annotations

from googleapiclient.http import MediaInMemoryUpload

from tests._fakes.drive import FakeDrive


def test_create_then_get_media_round_trip():
    drive = FakeDrive()
    media = MediaInMemoryUpload(b"hello world", mimetype="text/markdown")
    created = (
        drive.files()
        .create(
            body={"name": "page.md", "parents": ["folder1"]},
            media_body=media,
            fields="id,headRevisionId,modifiedTime",
        )
        .execute()
    )
    assert created["id"]
    assert created["headRevisionId"] == "rev1"
    assert created["modifiedTime"]

    content = drive.files().get_media(fileId=created["id"]).execute()
    assert content == b"hello world"


def test_list_files_filters_by_name_and_parent():
    drive = FakeDrive()
    drive._seed_file(name="a.md", parents=["folder1"], content=b"A")
    drive._seed_file(name="b.md", parents=["folder1"], content=b"B")
    drive._seed_file(name="a.md", parents=["folder2"], content=b"OTHER")

    result = (
        drive.files()
        .list(
            q="name='a.md' and 'folder1' in parents and trashed=false",
            fields="files(id,headRevisionId,modifiedTime)",
        )
        .execute()
    )
    assert len(result["files"]) == 1
    assert result["files"][0]["headRevisionId"] == "rev1"


def test_list_files_lists_all_in_parent():
    drive = FakeDrive()
    drive._seed_file(name="a.md", parents=["folder1"], content=b"A")
    drive._seed_file(name="b.md", parents=["folder1"], content=b"B")
    drive._seed_file(name="x.md", parents=["folder2"], content=b"X")

    result = (
        drive.files()
        .list(
            q="'folder1' in parents and trashed=false",
            fields="files(id,name)",
        )
        .execute()
    )
    names = sorted(f["name"] for f in result["files"])
    assert names == ["a.md", "b.md"]


def test_update_bumps_revision_and_replaces_content():
    drive = FakeDrive()
    media1 = MediaInMemoryUpload(b"v1", mimetype="text/markdown")
    created = (
        drive.files()
        .create(
            body={"name": "p.md", "parents": ["f"]},
            media_body=media1,
            fields="id,headRevisionId",
        )
        .execute()
    )
    fid = created["id"]
    assert created["headRevisionId"] == "rev1"

    media2 = MediaInMemoryUpload(b"v2-longer", mimetype="text/markdown")
    updated = (
        drive.files().update(fileId=fid, media_body=media2, fields="id,headRevisionId").execute()
    )
    assert updated["headRevisionId"] == "rev2"

    content = drive.files().get_media(fileId=fid).execute()
    assert content == b"v2-longer"
