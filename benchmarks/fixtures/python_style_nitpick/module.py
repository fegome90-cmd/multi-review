"""Module with style nitpicks that should be suppressed."""

# Missing docstring for module-level variable
CONFIG_VALUE = "some_config"

def processData(data):  # naming: should be snake_case
    """Process some data."""
    # redundant variable
    temp = data
    result = temp.upper()
    return result

class dataProcessor:  # naming: should be PascalCase
    """Process data objects."""

    def __init__(self, name):
        self.name = name

    def doWork(self):  # naming: should be snake_case
        """Do some work."""
        # unused variable
        unused_var = 42
        return f"Processing {self.name}"

# formatting: extra whitespace


def another_function():
    """Another function with style issues."""
    x=1+2  # missing spaces around operators
    return x
