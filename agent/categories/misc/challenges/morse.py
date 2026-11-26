"""Morse code. The flag (letters and digits) is encoded as Morse; braces are left as-is.
Decode it back."""

DESCRIPTION = "A message was encoded in Morse code. Decode it back (the result is all lowercase)."

_MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.",
    "g": "--.", "h": "....", "i": "..", "j": ".---", "k": "-.-", "l": ".-..",
    "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-",
    "y": "-.--", "z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}


def make(flag: str) -> str:
    parts = []
    for c in flag:  # flag is already lowercase
        if c in _MORSE:
            parts.append(_MORSE[c])
        else:  # braces and any other punctuation pass through
            parts.append(c)
    return f"{DESCRIPTION}\nmorse (letters separated by spaces): {' '.join(parts)}"
