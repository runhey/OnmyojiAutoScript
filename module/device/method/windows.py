

from module.device.env import IS_WINDOWS


if IS_WINDOWS:
    from module.device.method.windows_impl import Window
    print("dd")

else:
    class Window:
        pass







