from incant import is_subclass


def test_is_subclass() -> None:
    """Our version of issubclass is safe."""
    # This would have been an exception in the original issubclass.
    assert not is_subclass(int, 1)
