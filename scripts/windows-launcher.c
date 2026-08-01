#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show) {
    wchar_t executable[MAX_PATH], root[MAX_PATH], script[MAX_PATH], arguments[MAX_PATH * 2];
    if (!GetModuleFileNameW(NULL, executable, MAX_PATH)) return 1;
    wcscpy_s(root, MAX_PATH, executable);
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = L'\0';
    swprintf_s(script, MAX_PATH, L"%ls\\scripts\\bootstrap-windows.ps1", root);
    swprintf_s(arguments, MAX_PATH * 2, L"-NoProfile -ExecutionPolicy Bypass -File \"%ls\"", script);
    HINSTANCE result = ShellExecuteW(NULL, L"open", L"powershell.exe", arguments, root, SW_SHOWNORMAL);
    if ((INT_PTR)result <= 32) {
        MessageBoxW(NULL, L"无法启动 PowerShell 安装程序。", L"赚钱音浪启动失败", MB_ICONERROR);
        return 1;
    }
    return 0;
}
