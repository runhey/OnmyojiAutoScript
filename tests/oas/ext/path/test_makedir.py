import os
import shutil

import pytest

from oas.ext.env import OAS_ROOT
from oas.ext.path.calc import joinpath, normpath
from oas.ext.path.makedir import _convert_path, _get_parent_folder, _iter_parent_folder, batch_makedirs


@pytest.fixture(scope='module')
def temp_dir():
    """
    Create a temporary test folder under ALASIO_ROOT,
    removed after all tests in this module finish

    Yields:
        str: Absolute path of the temporary test folder
    """
    folder = joinpath(normpath(OAS_ROOT), 'test_makedir_tmp')
    shutil.rmtree(folder, ignore_errors=True)
    os.mkdir(folder)
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


class TestConvertPath:
    """Tests for _convert_path()."""

    def test_relative_to_absolute(self):
        """Relative filepath should be converted to absolute."""
        cwd = normpath(os.getcwd())
        assert list(_convert_path(['a/b/c.txt'])) == [joinpath(cwd, 'a/b/c.txt')]

    def test_mixed(self):
        """Relative and absolute filepaths should both be converted."""
        cwd = normpath(os.getcwd())
        abs_path = 'C:/a/b.txt' if os.sep == '\\' else '/a/b.txt'
        assert list(_convert_path(['a/b/c.txt', abs_path])) == [joinpath(cwd, 'a/b/c.txt'), abs_path]

    def test_absolute_unchanged(self):
        """Absolute filepath should stay unchanged."""
        abs_path = 'C:/a/b.txt' if os.sep == '\\' else '/a/b.txt'
        assert list(_convert_path([abs_path])) == [abs_path]

    @pytest.mark.skipif(os.sep != '\\', reason='backslash is a path separator on Windows only')
    def test_normalize_backslash(self):
        """Windows-style backslash paths should be normalized."""
        cwd = normpath(os.getcwd())
        assert list(_convert_path([r'a\b\c.txt'])) == [joinpath(cwd, 'a/b/c.txt')]

    def test_empty(self):
        """Empty input should return an empty list."""
        assert list(_convert_path([])) == []


class TestIterParentFolder:
    """Tests for _iter_parent_folder()."""

    def test_single_level(self):
        """Filepath should yield all parent folders, from deep to shallow."""
        assert list(_iter_parent_folder('a/b/c.txt')) == ['a/b', 'a']

    def test_deep(self):
        """Nested filepath should yield all ancestor folders."""
        assert list(_iter_parent_folder('a/b/c/d.txt')) == ['a/b/c', 'a/b', 'a']

    def test_no_folder(self):
        """Filepath without a parent folder should yield nothing."""
        assert list(_iter_parent_folder('file.txt')) == []

    def test_drive_root(self):
        """Windows drive root should be yielded as the last folder."""
        assert list(_iter_parent_folder('C:/folder/file.txt')) == ['C:/folder', 'C:']

    def test_absolute_path(self):
        """Absolute filepath should stop before the root."""
        assert list(_iter_parent_folder('/a/b/c.txt')) == ['/a/b', '/a']


class TestGetParentFolder:
    """Tests for _get_parent_folder()."""

    def test_single_parent(self):
        """One filepath should return its parent folder and ancestors."""
        assert _get_parent_folder(['a/b/c.txt']) == ['a', 'a/b']

    def test_deep_parent(self):
        """Nested filepath should return all ancestor folders."""
        assert _get_parent_folder(['a/b/c/d.txt']) == ['a', 'a/b', 'a/b/c']

    def test_dedupe(self):
        """Filepaths in the same folder should be deduplicated."""
        assert _get_parent_folder(['a/b/x.txt', 'a/b/y.txt']) == ['a', 'a/b']

    def test_skip_when_ancestor_added(self):
        """If a folder was added before, remaining ancestors should be skipped."""
        assert _get_parent_folder(['a/b/c.txt', 'a/b/d.txt']) == ['a', 'a/b']

    def test_skip_keeps_new_branches(self):
        """Skipping a known folder should still add new deeper branches."""
        assert _get_parent_folder(['a/b/x.txt', 'a/b/y/c.txt']) == ['a', 'a/b', 'a/b/y']

    def test_multiple_folders(self):
        """Filepaths in different folders should all be returned."""
        assert set(_get_parent_folder(['a/b/x.txt', 'c/d.txt', 'a/b/y.txt'])) == {'a/b', 'a', 'c'}

    def test_sorted_shallow_to_deep(self):
        """Folders should be sorted from shallow to deep."""
        assert _get_parent_folder(['a/b/c.txt', 'a/b/d.txt']) == ['a', 'a/b']

    def test_no_folder(self):
        """Filepath without a parent folder should be skipped."""
        assert _get_parent_folder(['file.txt']) == []

    def test_empty(self):
        """Empty input should return an empty list."""
        assert _get_parent_folder([]) == []


class TestBatchMakedirs:
    """Tests for batch_makedirs()."""

    def test_create_parents(self, temp_dir):
        """Parent folders should be created, but not the filepath itself."""
        file = joinpath(temp_dir, 'test_create_parents/a/b/c.txt')
        batch_makedirs([file])
        assert os.path.isdir(joinpath(temp_dir, 'test_create_parents/a'))
        assert os.path.isdir(joinpath(temp_dir, 'test_create_parents/a/b'))
        assert not os.path.exists(file)

    def test_create_missing_ancestors(self, temp_dir):
        """Ancestors not in the folder list should be created as well."""
        file = joinpath(temp_dir, 'test_create_missing_ancestors/a/b/c/d.txt')
        batch_makedirs([file])
        assert os.path.isdir(joinpath(temp_dir, 'test_create_missing_ancestors/a'))
        assert os.path.isdir(joinpath(temp_dir, 'test_create_missing_ancestors/a/b/c'))

    def test_create_multiple(self, temp_dir):
        """Parents of multiple filepaths should be created."""
        batch_makedirs([
            joinpath(temp_dir, 'test_create_multiple/a/b/x.txt'),
            joinpath(temp_dir, 'test_create_multiple/a/b/y.txt'),
            joinpath(temp_dir, 'test_create_multiple/c/d/e.txt'),
        ])
        assert os.path.isdir(joinpath(temp_dir, 'test_create_multiple/a/b'))
        assert os.path.isdir(joinpath(temp_dir, 'test_create_multiple/c/d'))
        assert not os.path.exists(joinpath(temp_dir, 'test_create_multiple/c/d/e.txt'))

    def test_existing(self, temp_dir):
        """Existing folders should not raise errors."""
        root = joinpath(temp_dir, 'test_existing')
        os.makedirs(joinpath(root, 'a/b'))
        batch_makedirs([joinpath(root, 'a/b/c.txt'), joinpath(root, 'a/b/d.txt')])
        assert os.path.isdir(joinpath(root, 'a/b'))

    def test_existing_partial(self, temp_dir):
        """Missing folders should be created under existing ones."""
        root = joinpath(temp_dir, 'test_existing_partial')
        os.mkdir(root)
        os.mkdir(joinpath(root, 'a'))
        batch_makedirs([joinpath(root, 'a/b/c.txt')])
        assert os.path.isdir(joinpath(root, 'a/b'))

    def test_file_in_the_way(self, temp_dir):
        """A file at the folder path should be removed and replaced by a folder."""
        root = joinpath(temp_dir, 'test_file_in_the_way')
        os.mkdir(root)
        os.mkdir(joinpath(root, 'a'))
        file = joinpath(root, 'a/b')
        with open(file, 'w') as f:
            f.write('data')
        batch_makedirs([joinpath(root, 'a/b/c.txt')])
        assert os.path.isdir(file)
        assert not os.path.exists(joinpath(root, 'a/b/c.txt'))

    def test_deep_file_in_the_way(self, temp_dir):
        """A deep file in the way should be removed along with its ancestors."""
        root = joinpath(temp_dir, 'test_deep_file_in_the_way')
        os.mkdir(root)
        with open(joinpath(root, 'a'), 'w') as f:
            f.write('data')
        batch_makedirs([joinpath(root, 'a/b/c.txt')])
        assert os.path.isdir(joinpath(root, 'a'))
        assert os.path.isdir(joinpath(root, 'a/b'))
        assert not os.path.exists(joinpath(root, 'a/b/c.txt'))

    def test_absolute_path(self, temp_dir):
        """Absolute filepaths should work."""
        file = joinpath(temp_dir, 'test_absolute_path/x/y.txt')
        batch_makedirs([file])
        assert os.path.isdir(joinpath(temp_dir, 'test_absolute_path/x'))

    def test_empty_input(self, temp_dir):
        """Empty input should do nothing."""
        batch_makedirs([])

    def test_relative_under_subdir(self, temp_dir):
        """Relative filepaths should be created under the current directory."""
        work = joinpath(temp_dir, 'test_relative_under_subdir')
        os.mkdir(work)
        old = os.getcwd()
        try:
            os.chdir(work)
            batch_makedirs(['a/b/c.txt'])
            assert os.path.isdir(joinpath(work, 'a/b'))
            assert not os.path.exists(joinpath(work, 'a/b/c.txt'))
        finally:
            os.chdir(old)

    def test_no_folder(self, temp_dir):
        """Filepath without a parent folder should do nothing."""
        file = joinpath(temp_dir, 'test_no_folder.txt')
        batch_makedirs([file])
        assert not os.path.exists(file)
