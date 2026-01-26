class BaseAnalyzer:
    def __init__(self, rules):
        self.rules = rules

    def analyze_confidence(self, score, grade):
        raise NotImplementedError

    def analyze_target(self, score, target_grade):
        raise NotImplementedError
