from PyInstaller.utils.hooks import collect_dynamic_libs
binaries=collect_dynamic_libs('ctranslate2')
excludedimports=['ctranslate2.converters','ctranslate2.specs','torch','transformers','tensorflow']
