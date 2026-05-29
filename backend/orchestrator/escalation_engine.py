# figures out when G needs to pause and ask the parent for approval
# high-risk actions like deleting calendar events shouldnt just happen automatically


class EscalationEngine:
    def __init__(self) -> None:
        self.llm = None 
    
    


