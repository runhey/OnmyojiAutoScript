cmake_minimum_required(VERSION 3.16)

project(fluentui LANGUAGES CXX)

#配置通用编译
set(CMAKE_AUTOMOC ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(APPLE)
    set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING "" FORCE)
endif()

#设置可执行文件输出目录
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin/debug)
else()
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin/release)
endif()

#设置版本号
add_definitions(-DVERSION=1,2,9,0)

find_package(Qt6 REQUIRED COMPONENTS Core Quick Qml)

#遍历所有Cpp文件
file(GLOB_RECURSE CPP_FILES *.cpp *.h)
foreach(filepath ${CPP_FILES})
    string(REPLACE "${CMAKE_CURRENT_SOURCE_DIR}/" "" filename ${filepath})
    list(APPEND sources_files ${filename})
endforeach(filepath)

#遍历所有qml文件
file(GLOB_RECURSE QML_PATHS *.qml)
foreach(filepath ${QML_PATHS})
    string(REPLACE "${CMAKE_CURRENT_SOURCE_DIR}/" "" filename ${filepath})
    list(APPEND qml_files ${filename})
endforeach(filepath)

#遍历所有资源文件
file(GLOB_RECURSE RES_PATHS *.png *.jpg *.svg *.ico *.ttf *.webp)
foreach(filepath ${RES_PATHS})
    string(REPLACE "${CMAKE_CURRENT_SOURCE_DIR}/" "" filename ${filepath})
    list(APPEND resource_files ${filename})
endforeach(filepath)

#修改资源文件导出路径
foreach(filepath IN LISTS qml_files resource_files)
    string(REPLACE "imports/FluentUI/" "" filename ${filepath})
    set_source_files_properties(${filepath} PROPERTIES QT_RESOURCE_ALIAS ${filename})
endforeach()

#添加qml模块
qt_add_qml_module(fluentui
    OUTPUT_DIRECTORY ${CMAKE_PREFIX_PATH}/qml/FluentUI
    VERSION 1.0
    URI "FluentUI"
    SOURCES ${sources_files} fluentui.rc
    QML_FILES ${qml_files}
    RESOURCES ${resource_files}
)

#链接库
target_link_libraries(fluentui PUBLIC
    Qt::Core
    Qt::Quick
    Qt::Qml
)

#链接库 win32库 不然mingw会编译错误
if(WIN32)
    target_link_libraries(fluentui PRIVATE dwmapi user32)
endif()
