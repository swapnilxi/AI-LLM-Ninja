#!/usr/bin/env python
import sys
import warnings
import os
from datetime import datetime

from research_crew.crew import ResearchCrew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

# Ensure the results folder exists
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Update the save_to_file function
def save_to_file(question, content):
    """
    Save content to a markdown file in the results folder with a unique name.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{question}_{timestamp}.md"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, "w") as file:
        file.write(content)

def run():
    """
    Run the crew.
    """
    inputs = {
        'topic': 'AI LLMs',
        'current_year': str(datetime.now().year)
    }
    
    try:
        result = ResearchCrew().crew().kickoff(inputs=inputs)
        save_to_file("run_results.txt", str(result))
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")

def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs"
    }
    try:
        result = ResearchCrew().crew().train(
            n_iterations=int(sys.argv[1]), 
            filename=sys.argv[2], 
            inputs=inputs
        )
        save_to_file("train_results.txt", str(result))
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        result = ResearchCrew().crew().replay(task_id=sys.argv[1])
        save_to_file("replay_results.txt", str(result))
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    try:
        result = ResearchCrew().crew().test(
            n_iterations=int(sys.argv[1]), 
            openai_model_name=sys.argv[2], 
            inputs=inputs
        )
        save_to_file("test_results.txt", str(result))
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")