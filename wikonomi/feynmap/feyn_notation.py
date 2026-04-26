class FeynNotator:
    # Pre-existing semantic symbols for LLM intuition
    SYMBOLS = {
        "PROPAGATOR": "γ",  # The Request/Trigger
        "VERTEX": "V",      # The Logic Hub
        "TRANSFORM": "⊗",   # The Data Formatter
        "PARTICLE": "P",    # The Persistent State
        "VIRTUAL": "~"      # The Async Event
    }

    @classmethod
    def generate_string(cls, trace):
        """Converts interaction steps into a Feynman String."""
        parts = []
        for role, name in trace:
            symbol = cls.SYMBOLS.get(role, "?")
            parts.append(f"{symbol}[{name}]")
        
        return " -> ".join(parts)