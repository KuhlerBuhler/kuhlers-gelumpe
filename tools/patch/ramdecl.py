"""The RAM entries of a patch (`ram`, `shares`; src/ramspans.mjs), written the same way by every builder."""


def area(at, length, what, source):
    """RAM of the patch's own: `source` is "<builder>:<SYMBOL>", where its size is set."""
    return {"at": f"{at:#010X}".replace("0X", "0x"), "length": length, "what": what, "source": source}


def share(at, length, owner, what, source):
    """A word that lies in an area the patch `owner` declares."""
    return {**area(at, length, what, source), "with": owner}
