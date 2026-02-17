import os
from openai import AzureOpenAI

endpoint = "https://ddft-models-resource.cognitiveservices.azure.com/"
model_name = "gpt-5.1"
deployment = "gpt-5.1"

subscription_key = "FLO9FdGLxqSlSgWk7cAhapNmHPvCAMzYRMkA74q2hvZhnGa5w3CGJQQJ99BKACHYHv6XJ3w3AAAAACOGhWzt"
api_version = "2024-12-01-preview"

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

response = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": "I am going to Paris, what should I see?",
        }
    ],
    max_completion_tokens=16384,
    model=deployment
)

print(response.choices[0].message.content)
