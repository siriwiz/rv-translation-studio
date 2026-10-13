"""Build with Studio's native-runtime bootstrap in the DLL scanner as well."""
import PyInstaller.__main__
import PyInstaller.building.build_main as build_main

original_find=build_main.find_binary_dependencies


def find_with_bootstrap(binaries,import_packages,symlink_suppression_patterns):
    # PyInstaller imports every package in one isolated process to discover DLL
    # directories. Preload the same compatible MSVC runtime as main.py before
    # packages such as OpenCV can load an older bundled copy.
    packages=['desktop']+[name for name in import_packages if name!='desktop']
    return original_find(binaries,packages,symlink_suppression_patterns)


build_main.find_binary_dependencies=find_with_bootstrap
PyInstaller.__main__.run()
