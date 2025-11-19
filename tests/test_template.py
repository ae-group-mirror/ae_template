""" ae.template unit tests """
import os
import textwrap

import pytest

from ae.base import (
    DEF_PROJECT_PARENT_FOLDER, PY_EXT, TEMPLATES_FOLDER,
    norm_path, os_path_isfile, os_path_join, read_file, write_file)

from ae.template import (
    LOCK_EXT, OUTSOURCED_FILE_NAME_PREFIX, OUTSOURCED_MARKER,
    TPL_FILE_NAME_PREFIX, TPL_STOP_CNV_PREFIX,
    TEMPLATE_PLACEHOLDER_ID_PREFIX, TEMPLATE_PLACEHOLDER_ID_SUFFIX,
    TEMPLATE_PLACEHOLDER_ARGS_SUFFIX, TEMPLATE_INCLUDE_FILE_PLACEHOLDER_ID,
    deploy_destination_file_creator, deploy_template, patch_outsourced, patch_string,
    replace_with_file_content_or_default, replace_with_template_args)


def test_declaration_of_template_vars():
    assert isinstance(OUTSOURCED_FILE_NAME_PREFIX, str)
    assert isinstance(OUTSOURCED_MARKER, str)
    assert isinstance(TPL_FILE_NAME_PREFIX, str)
    assert isinstance(TEMPLATE_PLACEHOLDER_ID_PREFIX, str)
    assert isinstance(TEMPLATE_PLACEHOLDER_ID_SUFFIX, str)
    assert isinstance(TEMPLATE_PLACEHOLDER_ARGS_SUFFIX, str)
    assert isinstance(TEMPLATE_INCLUDE_FILE_PLACEHOLDER_ID, str)


class TestHelpers:
    def test_deploy_destination_file_creator_bytes_content(self, tmp_path):
        file_path = os_path_join(str(tmp_path),  'tst file name.bin')

        deploy_destination_file_creator(file_path, b"bytes content", extra_mode='b')

        assert os_path_isfile(file_path)
        assert read_file(file_path, extra_mode='b') == b"bytes content"

    def test_deploy_destination_file_creator_string_content(self, tmp_path):
        file_path = os_path_join(str(tmp_path), 'subdir1', 'subdir2', 'sub dir 3', 'tst file name')

        deploy_destination_file_creator(file_path, "string content", "")

        assert os_path_isfile(file_path)
        assert read_file(file_path) == "string content"

    def test_deploy_template_dst_files_not_passed(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        src_dir = os_path_join(parent_dir, 'tpl_src_prj_dir')
        tpl_dir = os_path_join(src_dir, TEMPLATES_FOLDER)
        file_name = 'template.extension'
        src_file = os_path_join(tpl_dir, file_name)
        content = "template file content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        write_file(src_file, content, make_dirs=True)
        os.makedirs(dst_dir)

        deploy_template(src_file, "", "", new_pdv)

        dst_file = os_path_join(dst_dir, file_name)
        assert os_path_isfile(dst_file)
        assert read_file(dst_file) == content

    def test_deploy_template_logged_state(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        src_dir = os_path_join(parent_dir, 'tpl_src_prj_dir')
        tpl_dir = os_path_join(src_dir, TEMPLATES_FOLDER)
        content = "logged template file content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        log_prefix = "    - "
        os.makedirs(tpl_dir)
        os.makedirs(dst_dir)
        logged = []

        file_name = "template_state_log.ext"
        src_file = os_path_join(tpl_dir, file_name)
        write_file(src_file, content)

        deploy_template(src_file, "", "", new_pdv, logger=lambda *_: logged.extend(arg for arg in _))
        assert logged[-1].startswith(log_prefix + "refresh")

        deploy_template(src_file, "", "", new_pdv, logger=lambda *_: logged.extend(arg for arg in _))
        assert logged[-1].startswith(log_prefix + "binary-exists-skip")

        lock_file = os_path_join(dst_dir, file_name + LOCK_EXT)
        write_file(lock_file, "")
        deploy_template(src_file, "", "", new_pdv, logger=lambda *_: logged.extend(arg for arg in _))
        assert logged[-1].startswith(log_prefix + "lock-extension-skip")
        os.remove(lock_file)

        src_file = os_path_join(tpl_dir, TPL_FILE_NAME_PREFIX + "template_state_log.ext")
        write_file(src_file, content)

        deploy_template(src_file, "", "", new_pdv, logger=lambda *_: logged.extend(arg for arg in _))
        assert logged[-1].startswith(log_prefix + "unchanged-skip")

        src_file = os_path_join(tpl_dir, TPL_FILE_NAME_PREFIX + "template_state_log.ext")
        write_file(src_file, content + " extended")

        deploy_template(src_file, "", "", new_pdv, logger=lambda *_: logged.extend(arg for arg in _))
        assert logged[-1].startswith(log_prefix + "missing-outsourced-marker-skip")

    def test_deploy_template_otf_in_sub_dir(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'prj_with_otf_tpl')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        sub_dir_folder = 'sub_dir'
        tpl_sub_dir = os_path_join(tpl_dir, sub_dir_folder)
        file_name = OUTSOURCED_FILE_NAME_PREFIX + 'changed_template' + PY_EXT
        src_file = os_path_join(tpl_sub_dir, file_name)
        content = "# template file content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        patcher = "patching package id to be added to patched destination file"
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        os.makedirs(dst_dir)

        deploy_template(src_file, sub_dir_folder, patcher, new_pdv, dst_files=dst_files)

        dst_file = os_path_join(dst_dir, sub_dir_folder, file_name[len(OUTSOURCED_FILE_NAME_PREFIX):])
        assert os_path_isfile(dst_file)
        assert OUTSOURCED_MARKER in read_file(dst_file)
        assert patcher in read_file(dst_file)
        assert read_file(dst_file).endswith(content)
        assert norm_path(dst_file) in dst_files

    def test_deploy_template_otf_tpl_in_sub_dir(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'prj_root_dir')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        sub_dir_folder = 'sub_dir'
        tpl_sub_dir = os_path_join(tpl_dir, sub_dir_folder)
        file_name = OUTSOURCED_FILE_NAME_PREFIX + TPL_FILE_NAME_PREFIX + 'changed_template' + PY_EXT
        src_file = os_path_join(tpl_sub_dir, file_name)
        content = "# template file content created in {project_path}"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        patcher = "patching project name to be added to destination file"
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        os.makedirs(dst_dir)

        deploy_template(src_file, sub_dir_folder, patcher, new_pdv, dst_files=dst_files)

        dst_file = os_path_join(dst_dir, sub_dir_folder,
                                file_name[len(OUTSOURCED_FILE_NAME_PREFIX) + len(TPL_FILE_NAME_PREFIX):])
        assert os_path_isfile(dst_file)
        assert OUTSOURCED_MARKER in read_file(dst_file)
        assert patcher in read_file(dst_file)
        assert read_file(dst_file).endswith(content.format(project_path=dst_dir))
        assert norm_path(dst_file) in dst_files

    def test_deploy_template_otf_stop_tpl(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'prj_root_dir')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        sub_dir_folder = TEMPLATES_FOLDER
        tpl_sub_dir = os_path_join(tpl_dir, sub_dir_folder)
        file_name = OUTSOURCED_FILE_NAME_PREFIX + TPL_STOP_CNV_PREFIX + TPL_FILE_NAME_PREFIX + 'chg_template' + PY_EXT
        src_file = os_path_join(tpl_sub_dir, file_name)
        content = "# template file content created in {project_path}"
        dst_dir = os_path_join(parent_dir, 'dst', TEMPLATES_FOLDER)
        new_pdv = {'project_path': dst_dir}
        patcher = "patcher"
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        os.makedirs(dst_dir)

        deploy_template(src_file, sub_dir_folder, patcher, new_pdv, dst_files=dst_files)

        dst_file = os_path_join(dst_dir, sub_dir_folder,
                                file_name[len(OUTSOURCED_FILE_NAME_PREFIX) + len(TPL_STOP_CNV_PREFIX):])
        assert os_path_isfile(dst_file)
        assert OUTSOURCED_MARKER in read_file(dst_file)
        assert patcher in read_file(dst_file)
        assert read_file(dst_file).endswith(content)
        assert norm_path(dst_file) in dst_files

    def test_deploy_template_otf_existing_unlocked_because_marker(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'project_dir')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        file_name = OUTSOURCED_FILE_NAME_PREFIX + 'unlocked_template' + PY_EXT
        src_file = os_path_join(tpl_dir, file_name)
        content = f"# template file extra content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        patcher = "patching package id to be added to destination file"
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        dst_file = os_path_join(dst_dir, file_name[len(OUTSOURCED_FILE_NAME_PREFIX):])
        write_file(dst_file, OUTSOURCED_MARKER, make_dirs=True)

        deploy_template(src_file, "", patcher, new_pdv, dst_files=dst_files)

        assert os_path_isfile(dst_file)
        assert OUTSOURCED_MARKER in read_file(dst_file)
        assert content in read_file(dst_file)
        assert patcher in read_file(dst_file)
        assert norm_path(dst_file) in dst_files

    def test_deploy_template_otf_existing_locked_without_marker(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'prj_root')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        file_name = OUTSOURCED_FILE_NAME_PREFIX + 'locked_template' + PY_EXT
        src_file = os_path_join(tpl_dir, file_name)
        content = "# template file content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        patcher = "patcher id or package name"
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        dst_file = os_path_join(dst_dir, file_name[len(OUTSOURCED_FILE_NAME_PREFIX):])
        dst_content = "locked because not contains marker"
        write_file(dst_file, dst_content, make_dirs=True)

        deploy_template(src_file, "", patcher, new_pdv, dst_files=dst_files)

        assert os_path_isfile(dst_file)
        assert OUTSOURCED_MARKER not in read_file(dst_file)
        assert read_file(dst_file) == dst_content
        assert patcher not in read_file(dst_file)
        assert norm_path(dst_file) in dst_files

    def test_deploy_template_otf_locked_by_file(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'prj_dir')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        file_name = OUTSOURCED_FILE_NAME_PREFIX + 'locked_template' + PY_EXT
        src_file = os_path_join(tpl_dir, file_name)
        content = "# template file content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        dst_file = os_path_join(dst_dir, file_name[len(OUTSOURCED_FILE_NAME_PREFIX):])
        write_file(dst_file + '.locked', "", make_dirs=True)

        deploy_template(src_file, "", "", new_pdv, dst_files=dst_files)

        assert not os_path_isfile(dst_file)
        assert norm_path(dst_file) in dst_files

    def test_deploy_template_tpl_in_sub_dir(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'tpl_src_root_dir')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        sub_dir_folder = 'sub_dir'
        tpl_sub_dir = os_path_join(tpl_dir, sub_dir_folder)
        file_name = TPL_FILE_NAME_PREFIX + 'changed_template' + PY_EXT
        src_file = os_path_join(tpl_sub_dir, file_name)
        content = "# template file content created in {project_path}"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        patcher = "patching package id here not added to patched destination file"
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        os.makedirs(dst_dir)

        deploy_template(src_file, sub_dir_folder, patcher, new_pdv, dst_files=dst_files)

        dst_file = os_path_join(dst_dir, sub_dir_folder, file_name[len(TPL_FILE_NAME_PREFIX):])
        assert os_path_isfile(dst_file)
        assert OUTSOURCED_MARKER not in read_file(dst_file)
        assert patcher not in read_file(dst_file)
        assert read_file(dst_file).endswith(content.format(project_path=dst_dir))
        assert norm_path(dst_file) in dst_files

    def test_deploy_template_tpl_locked_by_priority(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        prj_dir = os_path_join(parent_dir, 'prj')
        tpl_dir = os_path_join(prj_dir, TEMPLATES_FOLDER)
        file_name = TPL_FILE_NAME_PREFIX + 'template' + PY_EXT
        src_file = os_path_join(tpl_dir, file_name)
        content = "# template file content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        os.makedirs(dst_dir)
        dst_file = os_path_join(dst_dir, file_name[len(TPL_FILE_NAME_PREFIX):])

        deploy_template(src_file, "", "", new_pdv, dst_files=dst_files)

        assert os_path_isfile(dst_file)
        assert read_file(dst_file) == content
        assert norm_path(dst_file) in dst_files

        dst_files_len = len(dst_files)
        write_file(src_file, 'any OTHER content')

        # second deploy try from tpl prj with lower priority
        deploy_template(src_file, "", "", new_pdv, dst_files=dst_files)

        assert os_path_isfile(dst_file)
        assert read_file(dst_file) == content
        assert dst_files_len == len(dst_files)

    def test_deploy_template_unchanged_in_sub_dir(self, tmp_path):
        parent_dir = os_path_join(str(tmp_path), DEF_PROJECT_PARENT_FOLDER)
        src_dir = os_path_join(parent_dir, 'tpl_src_prj_dir')
        tpl_dir = os_path_join(src_dir, TEMPLATES_FOLDER)
        sub_dir_folder = 'sub_dir'
        tpl_sub_dir = os_path_join(tpl_dir, sub_dir_folder)
        file_name = 'unchanged_template.ext'
        src_file = os_path_join(tpl_sub_dir, file_name)
        content = "template file content"
        dst_dir = os_path_join(parent_dir, 'dst')
        new_pdv = {'project_path': dst_dir}
        dst_files = set()
        write_file(src_file, content, make_dirs=True)
        os.makedirs(dst_dir)

        deploy_template(src_file, sub_dir_folder, "", new_pdv, dst_files=dst_files)

        dst_file = os_path_join(dst_dir, sub_dir_folder, file_name)
        assert os_path_isfile(dst_file)
        assert read_file(dst_file) == content
        assert norm_path(dst_file) in dst_files

    def test_patch_outsourced_md(self):
        content = "content"
        patcher = "patcher"
        patched_content = patch_outsourced("any.md", content, patcher)
        assert patched_content.endswith(content)
        assert patched_content.startswith(f"<!-- {OUTSOURCED_MARKER}")
        assert patcher in patched_content

    def test_patch_outsourced_rst(self):
        content = "content"
        patcher = "patcher"
        sep = os.linesep
        patched_content = patch_outsourced("any.rst", content, patcher)
        assert patched_content.endswith(content)
        assert patched_content.startswith(f"{sep}..{sep}    {OUTSOURCED_MARKER}")
        assert patcher in patched_content

    def test_patch_outsourced_txt(self):
        content = "content"
        patcher = "patcher"
        patched_content = patch_outsourced("any.txt", content, patcher)
        assert patched_content.endswith(content)
        assert patched_content.startswith(f"# {OUTSOURCED_MARKER}")
        assert patcher in patched_content

    def test_patch_string_empty_args(self):
        assert patch_string("", {}, invalid_place_holder_id=lambda s: "") == ""

    def test_patch_string_replace_without_empty_lines(self):
        # if sys.version_info < (3, 12):
        #    return  # backslash in f-strings is not supported before Python 3.12

        # code editor does allow comments with backslash at the end \
        tpl_content = textwrap.dedent('''\
        # ReplaceWith#({'1st line  # with comment\\n' if tpl_var else ''})#
        # ReplaceWith#({'2nd line\\n' if tpl_var else ''})#''')

        patched = patch_string(tpl_content, {'tpl_var': True})

        assert patched == "1st line  # with comment\n\n2nd line\n"
        assert patched == textwrap.dedent('''\
        1st line  # with comment
        
        2nd line
        ''')

        patched = patch_string(tpl_content, {'tpl_var': False})

        assert patched == "\n"

    def test_patch_string_with_globals(self):
        content = (
            "\nif {os.environ}:"                                    # patch_string is adding 'os' module to globals
            "\n    var_name = {tst_dict}"
        )
        key1 = 'key'
        val1 = "test dict key value"
        key2 = 'sub-dict'
        val2_key1 = 'sub_dict_key1'
        val2_key11 = 'sub_dict_key1'
        val2_val111 = "list item 1"
        val2_val112 = "list item 2"
        val2_key2 = 'str_val'
        val2_val2 = "string val"
        val2 = {val2_key1: {val2_key11: [val2_val111, val2_val112], val2_key2: val2_val2}}
        key3 = 'z quite long test dict key name, with z as first char to show on last line'
        val3 = "test dict value of long key name"

        patched = patch_string(content, {'tst_dict': {key1: val1, key2: val2, key3: val3}})

        assert key1 in patched
        assert val1 in patched
        assert key2 in patched
        assert val2_key1 in patched
        assert val2_key11 in patched
        assert val2_val111 in patched
        assert val2_val112 in patched
        assert val2_key2 in patched
        assert val2_val2 in patched
        assert key2 in patched
        assert val3 in patched

        assert 'os.environ' not in patched
        assert 'pprint.' not in patched
        assert 'sys.' not in patched

    def test_replace_with_file_content_or_default(self, tmp_path):
        assert replace_with_file_content_or_default("") == ""

        def_val = "default_value"
        assert replace_with_file_content_or_default(f"_non_file,{def_val}") == def_val
        assert replace_with_file_content_or_default(f"_non_file,{def_val},{def_val}") == def_val + "," + def_val

        assert replace_with_file_content_or_default(f"_non_file,'{def_val[:3]}' + '{def_val[3:]}'") == def_val
        assert replace_with_file_content_or_default(f"_non_file,369") == 369
        with pytest.raises(ValueError):
            assert replace_with_file_content_or_default(f"_non_file,{'a': 111}")
        with pytest.raises(ValueError):
            assert replace_with_file_content_or_default(f"_non_file,{3: '111'}")
        assert replace_with_file_content_or_default(f"_non_file,{111}") == 111
        assert replace_with_file_content_or_default(f"_non_file,[111]") == [111]
        assert replace_with_file_content_or_default(f"_non_file,(1, 2, 3)") == (1, 2, 3)

        syntax_err = "syntax error ' + 1"
        assert replace_with_file_content_or_default("_non_file," + syntax_err) == syntax_err

        file_name = os_path_join(str(tmp_path), "returned_file.txt")
        content = "file_content_to_be_returned"
        assert replace_with_file_content_or_default(f"{file_name},{def_val}") == def_val
        write_file(file_name, content)
        assert replace_with_file_content_or_default(file_name) == content
        assert replace_with_file_content_or_default(f"{file_name},{def_val}") == content

    def test_replace_with_template_args(self):
        any_arg_str = 'any Arg String'
        assert replace_with_template_args(any_arg_str) == any_arg_str
