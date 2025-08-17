from crewai import Agent, Task, Crew
from langchain_community.llms import Ollama
from video_feed import capture_frame
from vision import caption_image
from speech import transcribe_voice, speak_text

llm = Ollama(model="mistral:7b-instruct")

agent = Agent(
    role="Visual Assistant",
    goal="Answer user questions based on visual context",
    backstory="I assist users by interpreting visual data and voice commands.",
    llm=llm,
    allow_delegation=False
)

def main():
    image = capture_frame()
    caption = caption_image(image)
    voice_command = transcribe_voice()

    task = Task(
        description=f"Given this visual description: '{caption}', respond accurately to user's query: '{voice_command}'",
        agent=agent
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )

    response = crew.kickoff()
    print(f"Agent Response: {response}")

    # Speak out the response
    speak_text(response)

if __name__ == "__main__":
    main()
