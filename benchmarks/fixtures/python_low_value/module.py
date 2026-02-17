"""Module with low-value findings (low confidence + low severity)."""

# Low confidence suggestion
maybe_unused = "this might be unused"  # confidence: 20, severity: low

def possibly_improve():
    """Function that might need improvement.

    This is a vague suggestion with low confidence.
    """
    x = 1  # could be better named, but who knows
    return x

class MaybeUseful:
    """Class that might be useful.

    Could potentially be refactored but not sure.
    """

    def do_something(self):
        """Does something maybe."""
        pass
