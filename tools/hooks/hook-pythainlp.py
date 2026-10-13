"""Only the offline Thai word list is needed for line breaking."""
from PyInstaller.utils.hooks import collect_data_files
datas=collect_data_files('pythainlp',includes=['corpus/words_th.txt','corpus/stopwords_th.txt','corpus/syllables_th.txt','corpus/README.md','corpus/*.license'])
excludedimports=['transformers','tensorflow','sklearn','nltk','spacy','sentencepiece','huggingface_hub',
    'pythainlp.tokenize.attacut','pythainlp.tokenize.deepcut','pythainlp.tokenize.crfcut',
    'pythainlp.tokenize.oskut','pythainlp.tokenize.sefr_cut','pythainlp.tokenize.wtp',
    'pythainlp.tokenize.wangchanberta','pythainlp.tokenize.nercut']
