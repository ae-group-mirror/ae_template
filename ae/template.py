""" ae.template

"""
import os
from typing import Callable, Optional, Union, Any

from ae.base import (                                                                       # type: ignore
    norm_path, os_path_basename, os_path_isfile, os_path_join, os_path_splitext, read_file, write_file)
from ae.dynamicod import try_eval                                                           # type: ignore
from ae.literal import Literal                                                              # type: ignore


__version__ = '0.3.1'


LOCK_EXT = '.locked'                                    #: additional file extension to block updates from templates

OUTSOURCED_MARKER = 'THIS FILE IS EXCLUSIVELY MAINTAINED'
""" to mark the content (header) of an outsourced project file that gets created and updated from a template. """
OUTSOURCED_FILE_NAME_PREFIX = 'de_otf_'
""" file name prefix of an outsourced/externally maintained file, that get created and updated from a template. """
SKIP_IF_PORTION_DST_NAME_PREFIX = 'de_sfp_'
""" template file/path name prefix to skip deployment of template to namespace portion. will be removed from destination
file name by :func:`deploy_template`, but the check if the destination project is a namespace portion has to be done
externally, by not calling the :func:`deploy_template` function for templates with this prefix.
"""
SKIP_PRJ_TYPE_FILE_NAME_PREFIX = 'de_spt_'
""" file name prefix followed by a project type id (see *_PRJ constants). file creation/update from template will be
skipped if it the project type id in the template file name matches the destination project type.
"""

# these TEMPLATE_* constants get added by :class:`ProjectDevVars` to be used/recognized by :func:`refresh_templates`
TEMPLATE_PLACEHOLDER_ID_PREFIX = "# "                   #: template id prefix marker
TEMPLATE_PLACEHOLDER_ID_SUFFIX = "#("                   #: template id suffix marker
TEMPLATE_PLACEHOLDER_ARGS_SUFFIX = ")#"                 #: template args suffix marker
TEMPLATE_INCLUDE_FILE_PLACEHOLDER_ID = "IncludeFile"    #: :func:`replace_with_file_content_or_default`
TEMPLATE_REPLACE_WITH_PLACEHOLDER_ID = "ReplaceWith"    #: :func:`replace_with_template_args`

TPL_FILE_NAME_PREFIX = 'de_tpl_'                        #: file name prefix if template contains f-strings

TPL_STOP_CNV_PREFIX = '_z_'                             #: file name prefix to support template of template

TEMPLATES_FILE_NAME_PREFIXES = (
    OUTSOURCED_FILE_NAME_PREFIX, SKIP_IF_PORTION_DST_NAME_PREFIX, SKIP_PRJ_TYPE_FILE_NAME_PREFIX,
    TPL_FILE_NAME_PREFIX, TPL_STOP_CNV_PREFIX)
""" supported template file name prefixes (in the order they have to specified, apart from :data:`TPL_STOP_CNV_PREFIX`
which can be specified anywhere, to deploy template files to other template projects).

.. hint::
    :data:`SKIP_IF_PORTION_DST_NAME_PREFIX` can also be path name prefix, like :data:`MOVE_TPL_TO_PKG_PATH_NAME_PREFIX`.
"""


# types ---------------------------------------------------------------------------------------------------------------

Replacer = Callable[[str], str]                         #: template content replacer function type

TplVars = dict[str, Any]                                #: template placeholder variables to be replaced by its value


# global helpers  -----------------------------------------------------------------------------------------------------


def deploy_destination_file_creator(file_path: str, new_content: Union[str, bytes], extra_mode: str):
    """ create a destination file (created from a template) and the folders specified in the file path.

    :param file_path:           path of the file to create/update.
    :param new_content:         the new content of the file to create/update.
    :param extra_mode:          pass 'b' if the content is bytes (not string). for a more detailed description of this
                                parameter of the function :func:`ae.write_file`.
    """
    write_file(file_path, new_content, extra_mode=extra_mode, make_dirs=True)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches
def deploy_template(tpl_file_path: str, dst_path: str, patcher: str, tpl_vars: TplVars,
                    logger: Callable = print,
                    replacer: Optional[dict[str, Replacer]] = None,
                    dst_files: Optional[set[str]] = None,
                    creator: Callable[[str, Union[str, bytes], str], None] = deploy_destination_file_creator
                    ) -> bool:
    """ create/update outsourced project file content from a template.

    :param tpl_file_path:       template file path/name.ext (absolute or relative to the current working directory).
    :param dst_path:            absolute or relative destination path without the destination file name. relative paths
                                are relative to the project root path (the `project_path` item in the
                                :paramref:`~deploy_template.pdv` argument).
    :param patcher:             patching template project or function (to be added into the outsourced project file).
    :param tpl_vars:            template/project env/dev variables dict of the destination project to patch/refresh.
                                providing values for (1) f-string template replacements, and (2) to specify the project
                                type, and root or package data folder (in the `project_type`, and `project_path` or
                                `package_path` items).
    :param logger:              print()-like callable for logging.
    :param replacer:            optional dict with multiple replacer: key=placeholder-id and value=replacer callable.
    :param dst_files:           optional set of project file paths to be excluded from to be created/updated. if the
                                project file got created/updated by this function, then the destination file path will
                                be added to this set.
    :param creator:             optional destination file creator callable (default=:func:`_tpl_creator`).
                                specify a callable with the same parameters as :func:`_tpl_creator` to support remote
                                file system or for dry-run template checks (creating only a log of files to create).
    :return:                    boolean True if template got deployed/written to the destination, else False.

    .. note::
         the project file will be kept unchanged if either:

         * the absolute file path is in the set specified by the :paramref:`~deploy_template.dst_files` argument,
         * there exists a lock-file with the additional :data:`LOCK_EXT` file extension, or
         * the outsourced project text does not contain the :data:`OUTSOURCED_MARKER` string.

    """
    if replacer is None:
        replacer = {}
    if dst_files is None:
        dst_files = set()

    dst_file = os_path_basename(tpl_file_path)

    if dst_file.startswith(SKIP_IF_PORTION_DST_NAME_PREFIX):
        dst_file = dst_file[len(SKIP_IF_PORTION_DST_NAME_PREFIX):]

    if dst_file.startswith(SKIP_PRJ_TYPE_FILE_NAME_PREFIX):
        project_type, dst_file = dst_file[len(SKIP_PRJ_TYPE_FILE_NAME_PREFIX):].split('_', maxsplit=1)
        if project_type == tpl_vars['project_type']:
            logger(f"    - destination-project-type-skip ({project_type=}) of template {tpl_file_path}")
            return False

    outsourced = dst_file.startswith(OUTSOURCED_FILE_NAME_PREFIX)
    formatting = dst_file.startswith(TPL_FILE_NAME_PREFIX)
    mode = "" if outsourced or formatting else "b"

    new_content = read_file(tpl_file_path, extra_mode=mode)

    if outsourced:
        new_content = patch_outsourced(dst_file, new_content, patcher)
        dst_file = dst_file[len(OUTSOURCED_FILE_NAME_PREFIX):]
        formatting = dst_file.startswith(TPL_FILE_NAME_PREFIX)
    if formatting:
        new_content = patch_string(new_content, tpl_vars, **replacer)
        dst_file = dst_file[len(TPL_FILE_NAME_PREFIX):]
    if dst_file.startswith(TPL_STOP_CNV_PREFIX):    # needed only for de_otf__z_de_tpl_*.* or _z_*.* template files
        dst_file = dst_file[len(TPL_STOP_CNV_PREFIX):]

    deployed = False
    dst_path = os_path_join(tpl_vars.get('project_path', ""), dst_path)   # project_path ignored on absolute dst_path
    dst_file = norm_path(os_path_join(dst_path, patch_string(dst_file, tpl_vars)))
    if dst_file in dst_files:
        deploy_state = "lower-priority-skip"
    else:
        dst_files.add(dst_file)
        if os_path_isfile(dst_file + LOCK_EXT):
            deploy_state = "lock-extension-skip"
        else:
            old_content = read_file(dst_file, extra_mode=mode) if os_path_isfile(dst_file) else b"" if mode else ""
            if old_content and mode:
                deploy_state = "binary-exists-skip"
            elif new_content == old_content:
                deploy_state = "unchanged-skip"
            elif not mode and old_content and OUTSOURCED_MARKER not in old_content:
                deploy_state = "missing-outsourced-marker-skip"
            else:
                creator(dst_file, new_content, mode)
                deploy_state = "refresh"
                deployed = True

    logger(f"    - {deploy_state} of template {tpl_file_path}")
    return deployed


def patch_outsourced(file_name: str, content: str, patcher: str) -> str:
    """ create/update the content of an outsourced text file (created from a template file).

    :param file_name:       the name (and path) of the file to create/update/patch.
    :param content:         the content of the file (without the outsourced marker).
    :param patcher:         the patching template package/project name/version, to be placed in the outsourced marker.
    :return:                the patched content of the text file (with updated outsource marker).
    """
    ext = os_path_splitext(file_name)[1]
    sep = os.linesep
    if ext == '.md':
        beg, end = "<!-- ", " -->"
    elif ext == '.rst':
        beg, end = f"{sep}..{sep}    ", sep
    else:
        beg, end = "# ", ""
    return f"{beg}{OUTSOURCED_MARKER} by the project {patcher}{end}{sep}{content}"


def patch_string(content: str, tpl_vars: TplVars, **replacer: Replacer) -> str:
    """ replace f-string / dynamic placeholders in content with variable values / return values of replacer callables.

    :param content:             f-string to patch (e.g., a template file's content).
    :param tpl_vars:            project env/dev vars dict with variables used as globals for f-string replacements.
    :param replacer:            optional kwargs dict with key/name=placeholder-id and value=replacer-callable.
                                to specify additional replacer and also to overwrite or to deactivate the default
                                template placeholder replacer specified in :data:`DEFAULT_TEMPLATE_PLACEHOLDERS`
    :return:                    string resulting from the evaluation of the specified content f-string and from the
                                default and additionally specified template :paramref;`~patch_string.replacer`.
    :raises Exception:          if evaluation of :paramref;`~patch_string.content` f-string failed (because of
                                missing-globals-NameError/SyntaxError/ValueError/...).
    """
    glo_vars = globals().copy()     # provide globals of this module, e.g., setup_kwargs_literal(), TEMPLATE_*, ...
    glo_vars.update(tpl_vars)       # provide vars, e.g., PDV_COMMIT_MSG_FILE_NAME for .gitignore/index.rst templates
    glo_vars['_add_base_globals'] = ""

    content = try_eval('f"""' + content.replace('"""', r'\"\"\"') + '"""', glo_vars=glo_vars)
    if not content:
        return ""
    content = content.replace(r'\"\"\"', '"""')     # recover docstring delimiters

    suffix = TEMPLATE_PLACEHOLDER_ARGS_SUFFIX
    len_suf = len(suffix)
    all_replacer = REPLACER_DEFAULT_TPL_PLACEHOLDERS
    all_replacer.update(replacer)
    for key, fun in all_replacer.items():
        prefix = TEMPLATE_PLACEHOLDER_ID_PREFIX + key + TEMPLATE_PLACEHOLDER_ID_SUFFIX
        len_pre = len(prefix)

        beg = 0
        while True:
            beg = content.find(prefix, beg)
            if beg == -1:
                break

            end = content.find(suffix, beg)
            assert end != -1, f"patch_string() {key=} placeholder args-{suffix=} is missing in {content=}; {glo_vars=}"

            replacement = fun(content[beg + len_pre: end])
            if isinstance(replacement, str):
                content = content[:beg] + replacement + content[end + len_suf:]

    return content


def replace_with_file_content_or_default(args_str: str) -> str:
    """ return file content if the file specified in first string arg exists, else return empty string or 2nd arg str.

    :param args_str:            pass either file name, or file name and default literal separated by a comma character.
                                spaces, tabs, and newline characters get removed from the start/end of the file name.
                                a default literal gets parsed like a config variable, the literal value gets return.
    :return:                    file content or default literal value or empty string (if the file does not exist and
                                there is no comma char in :paramref:`~replace_with_file_content_or_default.args_str`).
    """
    file_name, *default = args_str.split(",", maxsplit=1)
    if file_name:
        file_name = file_name.split()[0]    # strip spaces, tabs, and newlines
    return read_file(file_name) if os_path_isfile(file_name) else Literal(default[0]).value if default else ""


def replace_with_template_args(args_str: str) -> str:
    """ template placeholder replacer function to hide uncompleted code from code-inspections/editor-warnings.

    :param args_str:            args string to return, replacing the template placeholder (interpreted as comment in
                                python code).
    :return:                    args string specified as argument of the :data:`TEMPLATE_REPLACE_WITH_PLACEHOLDER_ID`.
    """
    return args_str


REPLACER_DEFAULT_TPL_PLACEHOLDERS = {
    TEMPLATE_INCLUDE_FILE_PLACEHOLDER_ID: replace_with_file_content_or_default,
    TEMPLATE_REPLACE_WITH_PLACEHOLDER_ID: replace_with_template_args,
}
""" map of replacer callables used by :func:`patch_string`. """
