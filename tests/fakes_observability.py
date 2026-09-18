from contextlib import contextmanager

class FakeSpan:
    def __init__(self) -> None:
        self.attributes = {}
        self.errors = []

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def add_event(self, name, attributes=None) -> None:
        pass

    def record_exception(self, exc) -> None:
        self.errors.append(exc)

    def set_error(self, description) -> None:
        self.errors.append(description)

class FakeObservability:
    def __init__(self) -> None:
        self.span_names = []

    @contextmanager
    def span(self, name, attributes=None):
        self.span_names.append(name)
        yield FakeSpan()

class FakeInstrument:
    def __init__(self) -> None:
        self.values = []

    def add(self, value, attributes=None) -> None:
        self.values.append((value, attributes))

    def record(self, value, attributes=None) -> None:
        self.values.append((value, attributes))

class FakeMetrics:
    def __init__(self) -> None:
        self.tool_calls = FakeInstrument()
        self.tool_errors = FakeInstrument()
        self.tool_duration = FakeInstrument()