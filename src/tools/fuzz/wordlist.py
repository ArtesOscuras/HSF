def load_wordlist(path):
    words = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                word = line.strip()
                if word:
                    words.append(word)
    except (PermissionError, OSError):
        pass
    return words
