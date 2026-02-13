class BaseAnalyzer:
    def __init__(self, rules):
        self.rules = rules

    def analyze(self, score, grade, *, run_target=False):
        raise NotImplementedError
