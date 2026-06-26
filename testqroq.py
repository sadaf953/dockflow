import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# This lists all available models for your account
models = client.models.list()
for model in models.data:
    print(model.id)