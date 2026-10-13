# Studio uses the upstream tokenizer with packaged models, not the network/SBD API.
excludedimports=['argostranslate.translate','argostranslate.package','argostranslate.settings','argostranslate.sbd',
    'argostranslate.networking','argostranslate.apis','argostranslate.fewshot','argostranslate.models','spacy','stanza','torch']
