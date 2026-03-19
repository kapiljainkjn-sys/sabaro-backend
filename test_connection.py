import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

# Test OpenAI
print("Testing OpenAI...")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello in one word"}]
)
print("OpenAI works! Response:", response.choices[0].message.content)

# Test Supabase
print("\nTesting Supabase...")
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)
print("Supabase works!")

print("\n✅ All connected. Ready to build.")
