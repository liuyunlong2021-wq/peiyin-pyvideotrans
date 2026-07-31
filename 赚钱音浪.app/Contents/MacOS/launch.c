#include <dlfcn.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <wchar.h>

typedef wchar_t *(*py_decode_locale_fn)(const char *, size_t *);
typedef void (*py_set_program_name_fn)(const wchar_t *);
typedef int (*py_main_fn)(int, wchar_t **);

static int deployment_alert(void) {
    execl("/usr/bin/osascript", "osascript", "-e",
          "display alert \"赚钱音浪需要先完成本地部署\" message \"请在仓库目录执行 uv sync，然后再次双击此应用。\"",
          NULL);
    return 1;
}

int main(void) {
    char executable[PATH_MAX], executable_dir[PATH_MAX], repo_candidate[PATH_MAX];
    char repo[PATH_MAX], venv_python[PATH_MAX], python_real[PATH_MAX];
    char python_copy[PATH_MAX], python_base[PATH_MAX], libpython[PATH_MAX], script[PATH_MAX];
    uint32_t executable_size = sizeof(executable);

    if (_NSGetExecutablePath(executable, &executable_size) != 0)
        return deployment_alert();
    snprintf(executable_dir, sizeof(executable_dir), "%s", executable);
    snprintf(repo_candidate, sizeof(repo_candidate), "%s/../../..", dirname(executable_dir));
    if (!realpath(repo_candidate, repo))
        return deployment_alert();

    snprintf(venv_python, sizeof(venv_python), "%s/.venv/bin/python", repo);
    if (!realpath(venv_python, python_real))
        return deployment_alert();

    snprintf(python_copy, sizeof(python_copy), "%s", python_real);
    snprintf(python_base, sizeof(python_base), "%s", dirname(dirname(python_copy)));
    snprintf(libpython, sizeof(libpython), "%s/lib/libpython3.10.dylib", python_base);
    snprintf(script, sizeof(script), "%s/sp.py", repo);

    void *python = dlopen(libpython, RTLD_NOW | RTLD_GLOBAL);
    if (!python)
        return deployment_alert();

    py_decode_locale_fn py_decode_locale = (py_decode_locale_fn)dlsym(python, "Py_DecodeLocale");
    py_set_program_name_fn py_set_program_name = (py_set_program_name_fn)dlsym(python, "Py_SetProgramName");
    py_main_fn py_main = (py_main_fn)dlsym(python, "Py_Main");
    if (!py_decode_locale || !py_set_program_name || !py_main)
        return deployment_alert();

    wchar_t *program = py_decode_locale(venv_python, NULL);
    wchar_t *script_arg = py_decode_locale(script, NULL);
    if (!program || !script_arg || chdir(repo) != 0)
        return deployment_alert();

    wchar_t *argv[] = {program, script_arg, NULL};
    py_set_program_name(program);
    return py_main(2, argv);
}
