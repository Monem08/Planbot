"""
Plan Generator Core - Reused from CLI version
"""

import random
import json
import os
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime


class Category(Enum):
    STUDY = "study"
    FITNESS = "fitness"
    CODING = "coding"
    CREATIVE = "creative"
    PRODUCTIVITY = "productivity"


class Difficulty(Enum):
    EASY = (1, "Easy", 20)
    MEDIUM = (2, "Medium", 35)
    HARD = (3, "Hard", 50)
    
    def __init__(self, num: int, label: str, duration_base: int):
        self._value_ = num
        self.label = label
        self.duration_base = duration_base


STEP_POOLS = {
    Category.STUDY: [
        ("Review previous material", 2), ("Learn new concepts", 3),
        ("Practice with exercises", 2), ("Summarize key points", 1),
        ("Test your knowledge", 2), ("Watch tutorial", 1),
    ],
    Category.FITNESS: [
        ("Dynamic warm-up", 3), ("Main lift/strength work", 3),
        ("Cardio circuit", 2), ("Accessory work", 2),
        ("Cool-down stretches", 3), ("Foam rolling", 1),
    ],
    Category.CODING: [
        ("Review requirements", 2), ("Write failing test", 2),
        ("Implement feature", 3), ("Refactor code", 2),
        ("Document changes", 1), ("Deploy/verify", 1),
    ],
    Category.CREATIVE: [
        ("Gather inspiration", 2), ("Rough sketch/outline", 2),
        ("First draft", 3), ("Iterate/refine", 2), ("Final polish", 2),
    ],
    Category.PRODUCTIVITY: [
        ("Set priorities", 3), ("Deep work block", 3),
        ("Quick wins", 2), ("Review/adjust", 1), ("Prep for tomorrow", 2),
    ],
}

GOALS = {
    Category.STUDY: ["Master the topic", "Complete chapter", "Pass assessment"],
    Category.FITNESS: ["Build strength", "Improve endurance", "Mobility work"],
    Category.CODING: ["Ship feature", "Fix critical bug", "Learn new tech"],
    Category.CREATIVE: ["Finish draft", "Explore new style", "Complete project"],
    Category.PRODUCTIVITY: ["Clear backlog", "Organize workspace", "Plan week"],
}


@dataclass
class Step:
    name: str
    duration_minutes: int
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    id: int
    category: str
    difficulty: str
    goal: str
    steps: List[Step]
    created_at: str = ""
    
    @property
    def total_duration(self) -> int:
        return sum(s.duration_minutes for s in self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "difficulty": self.difficulty,
            "goal": self.goal,
            "total_duration": self.total_duration,
            "created_at": self.created_at,
            "steps": [s.to_dict() for s in self.steps],
        }


class PlanGenerator:
    _counter = 0
    
    def __init__(self):
        pass
    
    def _weighted_choice(self, options: List[Tuple[str, int]]) -> str:
        items, weights = zip(*options)
        return random.choices(items, weights=weights, k=1)[0]
    
    def _calculate_duration(self, difficulty: Difficulty, position: int, 
                          total: int) -> int:
        base = difficulty.duration_base
        if position == 0 or position == total - 1:
            return base // 2
        return int(base * random.uniform(0.8, 1.3))
    
    def generate(
        self,
        category: Optional[Category] = None,
        difficulty: Optional[Difficulty] = None,
        num_steps: Optional[int] = None,
    ) -> Plan:
        cat = category or random.choice(list(Category))
        diff = difficulty or random.choice(list(Difficulty))
        
        available = STEP_POOLS[cat]
        steps_count = min(num_steps or random.randint(3, 5), len(available))
        
        selected = []
        temp = available.copy()
        for _ in range(steps_count):
            choice = self._weighted_choice(temp)
            selected.append(choice)
            temp = [x for x in temp if x[0] != choice]
        
        steps = []
        for i, name in enumerate(selected):
            dur = self._calculate_duration(diff, i, steps_count)
            steps.append(Step(name=name, duration_minutes=dur))
        
        PlanGenerator._counter += 1
        
        return Plan(
            id=PlanGenerator._counter,
            category=cat.value,
            difficulty=diff.label,
            goal=random.choice(GOALS[cat]),
            steps=steps,
            created_at=datetime.now().isoformat(),
        )