#include "NativeEventFilter.h"
#include "FluTheme.h"
#include "FluApp.h"
#ifdef Q_OS_WIN
#pragma comment(lib, "Dwmapi.lib")
#pragma comment(lib, "User32.lib")
#include <Windows.h>
#include <windowsx.h>
#endif

bool NativeEventFilter::nativeEventFilter(const QByteArray &eventType, void *message, qintptr *result)
{
#ifdef Q_OS_WIN
    if (eventType == "windows_generic_MSG" && FluApp::fluTheme->frameless()) {
        MSG* msg = static_cast<MSG *>(message);
        if (msg == Q_NULLPTR)
            return false;
        if(!FluApp::fluApp->wnds.contains((WId)msg->hwnd)){
            return false;
        }
        switch(msg->message) {
        case WM_NCCALCSIZE:{
            NCCALCSIZE_PARAMS& params = *reinterpret_cast<NCCALCSIZE_PARAMS*>(msg->lParam);
            if (params.rgrc[0].top != 0)
                params.rgrc[0].top -= 1;
            *result = WVR_REDRAW;
            return true;
        }
        case WM_NCHITTEST: {
            auto view = FluApp::fluApp->wnds[(WId)msg->hwnd];
            bool isResize = !(view->maximumWidth()==view->minimumWidth()&&view->maximumHeight()==view->minimumHeight());
            const LONG borderWidth = 8;
            RECT winrect;
            GetWindowRect(msg->hwnd, &winrect);
            long x = GET_X_LPARAM(msg->lParam);
            long y = GET_Y_LPARAM(msg->lParam);
            if (x >= winrect.left && x < winrect.left + borderWidth &&
                    y < winrect.bottom && y >= winrect.bottom - borderWidth && isResize) {
                *result = HTBOTTOMLEFT;
                return true;
            }
            if (x < winrect.right && x >= winrect.right - borderWidth &&
                    y < winrect.bottom && y >= winrect.bottom - borderWidth && isResize) {
                *result = HTBOTTOMRIGHT;
                return true;
            }
            if (x >= winrect.left && x < winrect.left + borderWidth &&
                    y >= winrect.top && y < winrect.top + borderWidth && isResize) {
                *result = HTTOPLEFT;
                return true;
            }
            if (x < winrect.right && x >= winrect.right - borderWidth &&
                    y >= winrect.top && y < winrect.top + borderWidth && isResize) {
                *result = HTTOPRIGHT;
                return true;
            }
            if (x >= winrect.left && x < winrect.left + borderWidth && isResize) {
                *result = HTLEFT;
                return true;
            }
            if (x < winrect.right && x >= winrect.right - borderWidth && isResize) {
                *result = HTRIGHT;
                return true;
            }
            if (y < winrect.bottom && y >= winrect.bottom - borderWidth && isResize) {
                *result = HTBOTTOM;
                return true;
            }
            if (y >= winrect.top && y < winrect.top + borderWidth && isResize) {
                *result = HTTOP;
                return true;
            }
            return false;
        }
        default:
            break;
        }
    }
#endif
    return false;
}
