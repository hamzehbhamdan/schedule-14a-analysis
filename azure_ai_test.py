from openai import AzureOpenAI
    
client = AzureOpenAI(
    api_key="6dfe1fa62b0e40c6a9d0c31d19465ce2",  
    api_version="2023-12-01-preview",
    azure_endpoint="https://ai-hhamda818ai8293830821129539.openai.azure.com/openai/deployments/gpt-35-turbo/chat/completions?api-version=2023-03-15-preview"
)

completion = client.chat.completions.create(
    model="gpt-35-turbo", # This must match the custom deployment name you chose for your model.
    messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Who won the world series in 2020?"},
    {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
    {"role": "user", "content": "Where was it played?"}
  ]
)

print(completion.choices[0].message.content)