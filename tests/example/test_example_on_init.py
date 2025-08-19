from fport import example

def test_example_prints_expected_output(capsys):
    """example() should run without errors and print expected messages."""

    # Act: run the example. It contains its own assertions about the session state.
    example()

    # Assert: check key parts of the stdout
    captured = capsys.readouterr()
    out = captured.out

    # Must include the listener's log and the final result
    assert "Received: add" in out  # e.g., "Received: add, args=(2, 3), kwargs={}"
    assert "Result: 5" in out

    # No error messages expected on stderr
    assert captured.err == ""

