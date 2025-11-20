import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {
            "role": "user",
            "content": "You are QuotePilot, a quoting assistant for an industrial distributors. In one sentence, describe what you do."
        }
    ]
)

print(response.choices[0].message.content)

